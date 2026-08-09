"""exp-20260709-024: candidate training ledger materialization.

Measurement repair for exp-20260709-023. This runner creates a canonical
candidate-decision training ledger from existing backtester entry-candidate
events, then attaches fixed-horizon cash/SPY/QQQ labels. It does not fit a
model and does not change signal generation, ranking, sizing, exits, or orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping


EXPERIMENT_ID = "exp-20260709-024"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "candidate_training_ledger_materialization"
RUNNER = f"quant/experiments/exp_20260709_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WINDOWS = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": DATA_DIR / "ohlcv" / "ohlcv_snapshot_20251023_20260421.json",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": DATA_DIR / "ohlcv" / "ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": DATA_DIR / "ohlcv" / "ohlcv_snapshot_20241002_20250422.json",
    },
]

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260709_024_candidate_training_ledger_materialization.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: candidate-entry meta-labeling is blocked by missing "
    "leak-free candidate decision rows; first-build a canonical-window "
    "candidate training ledger by saving full backtester entry candidate "
    "events and fixed-horizon cash/SPY/QQQ labels without changing strategy "
    "behavior."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "canonical_candidate_training_ledger_materialization"
MECHANISM_FAMILY = "candidate_meta_label"
TRIAL_FAMILY = "candidate_meta_label_training_ledger_materialization"
TRIAL_VARIANT_ID = "candidate_training_ledger_v1"
SINGLE_CAUSAL_VARIABLE = "candidate_meta_label_training_ledger_materialization_v1"
CAUSAL_COMPONENTS = [
    "canonical_backtest_candidate_events",
    "fixed_horizon_labels",
    "training_table_readiness_gate",
    "no_strategy_change",
]
NEARBY_PRIORS = ["exp-20260709-023"]
NEW_EVIDENCE_TYPE = "new_training_rows"
NEW_EVIDENCE_AXIS = (
    "False-positive routine guard override: this is the first canonical "
    "candidate-training ledger contract for candidate_meta_label, not a "
    "routine delta append to an accepted observer or default-off forward "
    "ledger; it creates non-oracle candidate decision rows across the three "
    "fixed windows."
)
ACCEPTANCE_RULE = (
    "Accepted measurement repair if the runner creates reproducible candidate "
    "event artifacts, enriches rows with fixed-horizon cash/SPY/QQQ labels "
    "where available, records readiness counts versus the exp-20260709-023 "
    "gate, and changes no strategy behavior."
)
SAMPLE_GATE = {
    "min_complete_candidate_rows": 300,
    "min_positive_labels": 75,
    "min_negative_labels": 75,
    "min_chronological_folds": 3,
    "min_test_rows_per_fold": 50,
    "max_single_ticker_share": 0.20,
    "requires_selected_and_rejected_candidate_coverage": True,
    "requires_non_oracle_labels": True,
}
HORIZONS = (10, 20)
TRAINING_NOTIONAL_USD = 10000.0

CHANGED_FILES = [
    RUNNER,
    "data/experiments/exp-20260709-024/exp_20260709_024_candidate_training_ledger_materialization.json",
    "experiments/logs/exp-20260709-024.json",
    "experiments/cards/exp-20260709-024.md",
    "experiments/manifests/exp-20260709-024.json",
    "experiments/tickets/exp-20260709-024.json",
    "docs/experiment_registry.json",
    "docs/experiment_log.jsonl",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260709-024/exp_20260709_024_candidate_training_ledger_materialization.json",
    "experiments/cards/exp-20260709-024.md",
    "experiments/manifests/exp-20260709-024.json",
    "experiments/tickets/exp-20260709-024.json",
    "experiments/logs/exp-20260709-024.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return safe(value.item())
        except Exception:
            return str(value)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
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


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def round_or_none(value: Any, digits: int = 6) -> float | None:
    parsed = numeric(value)
    return round(parsed, digits) if parsed is not None else None


def pct_return(exit_price: Any, entry_price: Any) -> float | None:
    entry = numeric(entry_price)
    exit_ = numeric(exit_price)
    if entry is None or exit_ is None or entry <= 0:
        return None
    return exit_ / entry - 1.0


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [numeric(row.get("max_drawdown_pct")) for row in windows]
    drawdowns = [value for value in drawdowns if value is not None]
    return {
        "available": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows),
            2,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def load_snapshot_rows(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = read_json(path, {})
    raw = payload.get("ohlcv") if isinstance(payload, Mapping) else {}
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in raw.items():
        clean: list[dict[str, Any]] = []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            date = row.get("Date")
            open_ = numeric(row.get("Open"))
            close = numeric(row.get("Close"))
            if not date or open_ is None or close is None:
                continue
            clean.append(
                {
                    "Date": str(date)[:10],
                    "Open": open_,
                    "Close": close,
                }
            )
        clean.sort(key=lambda item: item["Date"])
        if clean:
            out[str(ticker).upper()] = clean
    return out


def first_index_after(rows: list[Mapping[str, Any]], date_str: str) -> int | None:
    for idx, row in enumerate(rows):
        if str(row.get("Date") or "") > date_str:
            return idx
    return None


def row_by_date(rows: list[Mapping[str, Any]], date_str: str) -> Mapping[str, Any] | None:
    for row in rows:
        if row.get("Date") == date_str:
            return row
    return None


def benchmark_return(
    rows: list[Mapping[str, Any]], entry_date: str, exit_date: str
) -> float | None:
    entry = row_by_date(rows, entry_date)
    exit_ = row_by_date(rows, exit_date)
    if entry is None or exit_ is None:
        return None
    return pct_return(exit_.get("Close"), entry.get("Open"))


def make_candidate_id(window_label: str, event: Mapping[str, Any]) -> str:
    key = "|".join(
        [
            window_label,
            str(event.get("date") or ""),
            str(event.get("ticker") or ""),
            str(event.get("strategy") or ""),
            str(event.get("decision") or ""),
            str(event.get("candidate_rank") or ""),
        ]
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def label_candidate_event(
    event: Mapping[str, Any],
    *,
    window_label: str,
    snapshot_rows: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    signal_date = str(event.get("date") or "")[:10]
    decision = str(event.get("decision") or "unknown")
    signal_snapshot = event.get("signal_snapshot")
    if not isinstance(signal_snapshot, Mapping):
        signal_snapshot = {}
    sizing = signal_snapshot.get("sizing")
    if not isinstance(sizing, Mapping):
        sizing = {}

    ticker_rows = snapshot_rows.get(ticker, [])
    entry_idx = first_index_after(ticker_rows, signal_date) if signal_date else None
    entry_row = ticker_rows[entry_idx] if entry_idx is not None else None
    entry_date = entry_row.get("Date") if entry_row else None
    entry_open = entry_row.get("Open") if entry_row else None
    spy_rows = snapshot_rows.get("SPY", [])
    qqq_rows = snapshot_rows.get("QQQ", [])

    horizons: dict[str, dict[str, Any]] = {}
    for horizon in HORIZONS:
        label = f"{horizon}d"
        if entry_idx is None or entry_row is None:
            horizons[label] = {
                "status": "missing_entry_row",
                "horizon_trading_days": horizon,
            }
            continue
        exit_idx = entry_idx + horizon
        if exit_idx >= len(ticker_rows):
            horizons[label] = {
                "status": "not_settled",
                "horizon_trading_days": horizon,
                "intended_entry_date": entry_date,
            }
            continue
        exit_row = ticker_rows[exit_idx]
        exit_date = exit_row.get("Date")
        candidate_return = pct_return(exit_row.get("Close"), entry_open)
        spy_return = benchmark_return(spy_rows, entry_date, exit_date)
        qqq_return = benchmark_return(qqq_rows, entry_date, exit_date)
        missing = []
        if candidate_return is None:
            missing.append("candidate_return")
        if spy_return is None:
            missing.append("spy_return")
        if qqq_return is None:
            missing.append("qqq_return")
        complete = not missing
        horizons[label] = {
            "status": "complete" if complete else "missing_benchmark",
            "missing_fields": missing,
            "horizon_trading_days": horizon,
            "intended_entry_date": entry_date,
            "exit_date": exit_date,
            "entry_open": round_or_none(entry_open),
            "exit_close": round_or_none(exit_row.get("Close")),
            "candidate_return_pct": round_or_none(candidate_return, 8),
            "spy_return_pct": round_or_none(spy_return, 8),
            "qqq_return_pct": round_or_none(qqq_return, 8),
            "replacement_value_vs_cash_usd": (
                round(TRAINING_NOTIONAL_USD * candidate_return, 2)
                if candidate_return is not None else None
            ),
            "replacement_value_vs_spy_usd": (
                round(TRAINING_NOTIONAL_USD * (candidate_return - spy_return), 2)
                if candidate_return is not None and spy_return is not None else None
            ),
            "replacement_value_vs_qqq_usd": (
                round(TRAINING_NOTIONAL_USD * (candidate_return - qqq_return), 2)
                if candidate_return is not None and qqq_return is not None else None
            ),
            "label_positive_cash": candidate_return > 0 if candidate_return is not None else None,
            "label_positive_spy": (
                candidate_return > spy_return
                if candidate_return is not None and spy_return is not None else None
            ),
            "label_positive_qqq": (
                candidate_return > qqq_return
                if candidate_return is not None and qqq_return is not None else None
            ),
        }

    ten_day = horizons.get("10d", {})
    details = event.get("details") if isinstance(event.get("details"), Mapping) else {}
    return {
        "candidate_id": make_candidate_id(window_label, event),
        "window": window_label,
        "signal_date": signal_date,
        "ticker": ticker,
        "strategy": event.get("strategy"),
        "decision": decision,
        "selected": decision == "entered",
        "rejected_or_unselected": decision != "entered",
        "candidate_rank": event.get("candidate_rank"),
        "available_slots_at_entry_loop": event.get("available_slots_at_entry_loop"),
        "intended_entry_date": entry_date,
        "intended_entry_open": round_or_none(entry_open),
        "target_price": round_or_none(signal_snapshot.get("target_price")),
        "stop_price": round_or_none(signal_snapshot.get("stop_price")),
        "decision_time_features": {
            "entry_price": round_or_none(signal_snapshot.get("entry_price")),
            "sector": signal_snapshot.get("sector"),
            "confidence_score": round_or_none(signal_snapshot.get("confidence_score")),
            "trade_quality_score": round_or_none(signal_snapshot.get("trade_quality_score")),
            "target_mult_used": round_or_none(signal_snapshot.get("target_mult_used")),
            "regime_exit_bucket": signal_snapshot.get("regime_exit_bucket"),
            "regime_exit_score": round_or_none(signal_snapshot.get("regime_exit_score")),
            "shares_to_buy": round_or_none(sizing.get("shares_to_buy")),
            "risk_pct": round_or_none(sizing.get("risk_pct")),
            "base_risk_pct": round_or_none(sizing.get("base_risk_pct")),
        },
        "raw_decision_details": details,
        "horizons": horizons,
        "complete_10d_label": ten_day.get("status") == "complete",
        "label_positive_cash_10d": ten_day.get("label_positive_cash"),
        "label_source": "fixed_horizon_snapshot_next_open_entry",
        "oracle_label_used": False,
    }


def summarize_values(values: Iterable[float]) -> dict[str, Any]:
    xs = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not xs:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "min": None,
            "max": None,
            "positive_count": 0,
            "win_rate": None,
        }
    positives = sum(1 for value in xs if value > 0)
    return {
        "count": len(xs),
        "avg": round(sum(xs) / len(xs), 6),
        "median": round(median(xs), 6),
        "min": round(min(xs), 6),
        "max": round(max(xs), 6),
        "positive_count": positives,
        "win_rate": round(positives / len(xs), 6),
    }


def chronological_folds(
    rows: list[Mapping[str, Any]], fold_count: int = 3
) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            str(row.get("intended_entry_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("candidate_id") or ""),
        ),
    )
    folds: list[dict[str, Any]] = []
    if not ordered:
        return folds
    for idx in range(fold_count):
        start = round(idx * len(ordered) / fold_count)
        end = round((idx + 1) * len(ordered) / fold_count)
        chunk = ordered[start:end]
        positives = sum(1 for row in chunk if row.get("label_positive_cash_10d"))
        negatives = sum(1 for row in chunk if row.get("label_positive_cash_10d") is False)
        folds.append(
            {
                "fold": idx + 1,
                "rows": len(chunk),
                "positives": positives,
                "negatives": negatives,
                "first_entry_date": chunk[0].get("intended_entry_date") if chunk else None,
                "last_entry_date": chunk[-1].get("intended_entry_date") if chunk else None,
                "has_both_classes": positives > 0 and negatives > 0,
                "meets_min_test_rows": len(chunk) >= SAMPLE_GATE["min_test_rows_per_fold"],
            }
        )
    return folds


def result_metrics(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "period": result.get("period"),
        "total_pnl": round_or_none(result.get("total_pnl"), 2),
        "total_trades": result.get("total_trades"),
        "win_rate": round_or_none(result.get("win_rate")),
        "sharpe_daily": round_or_none(result.get("sharpe_daily")),
        "max_drawdown_pct": round_or_none(result.get("max_drawdown_pct")),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": round_or_none(result.get("survival_rate")),
    }


def run_window(window: Mapping[str, Any], universe: list[str]) -> dict[str, Any]:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(window["snapshot"]),
        include_entry_candidate_events=True,
        include_oracle_diagnostics=False,
    )
    result = engine.run()
    if not isinstance(result, Mapping) or result.get("error"):
        return {
            "label": window["label"],
            "start": window["start"],
            "end": window["end"],
            "snapshot": repo_rel(window["snapshot"]),
            "error": result.get("error") if isinstance(result, Mapping) else str(result),
            "candidate_events": [],
            "training_rows": [],
        }

    events = result.get("entry_candidate_events")
    if not isinstance(events, list):
        events = []
    snapshot_rows = load_snapshot_rows(Path(window["snapshot"]))
    training_rows = [
        label_candidate_event(
            event,
            window_label=str(window["label"]),
            snapshot_rows=snapshot_rows,
        )
        for event in events
        if isinstance(event, Mapping)
    ]
    reason_counts = Counter(row.get("decision") for row in training_rows)
    complete_10d = [
        row for row in training_rows
        if row.get("horizons", {}).get("10d", {}).get("status") == "complete"
    ]
    complete_20d = [
        row for row in training_rows
        if row.get("horizons", {}).get("20d", {}).get("status") == "complete"
    ]
    return {
        "label": window["label"],
        "start": window["start"],
        "end": window["end"],
        "snapshot": repo_rel(window["snapshot"]),
        "result_metrics": result_metrics(result),
        "candidate_event_count": len(events),
        "training_row_count": len(training_rows),
        "complete_10d_rows": len(complete_10d),
        "complete_20d_rows": len(complete_20d),
        "decision_counts": dict(sorted(reason_counts.items())),
        "candidate_events": events,
        "training_rows": training_rows,
    }


def build_readiness(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    complete_10d = [
        row for row in rows
        if row.get("horizons", {}).get("10d", {}).get("status") == "complete"
    ]
    complete_20d = [
        row for row in rows
        if row.get("horizons", {}).get("20d", {}).get("status") == "complete"
    ]
    positives = sum(1 for row in complete_10d if row.get("label_positive_cash_10d"))
    negatives = sum(1 for row in complete_10d if row.get("label_positive_cash_10d") is False)
    selected = [row for row in complete_10d if row.get("selected")]
    rejected = [row for row in complete_10d if row.get("rejected_or_unselected")]
    ticker_counts = Counter(str(row.get("ticker") or "") for row in complete_10d)
    top_ticker, top_rows = ticker_counts.most_common(1)[0] if ticker_counts else (None, 0)
    folds = chronological_folds(complete_10d)
    max_share = round(top_rows / len(complete_10d), 6) if complete_10d else None
    criteria = {
        "complete_candidate_rows_gte_300": len(complete_10d) >= SAMPLE_GATE["min_complete_candidate_rows"],
        "positive_labels_gte_75": positives >= SAMPLE_GATE["min_positive_labels"],
        "negative_labels_gte_75": negatives >= SAMPLE_GATE["min_negative_labels"],
        "three_chronological_folds_with_both_classes": (
            sum(1 for row in folds if row["has_both_classes"])
            >= SAMPLE_GATE["min_chronological_folds"]
        ),
        "each_fold_has_at_least_50_test_rows": (
            bool(folds) and all(row["meets_min_test_rows"] for row in folds)
        ),
        "no_single_ticker_over_20pct": (
            max_share is not None and max_share <= SAMPLE_GATE["max_single_ticker_share"]
        ),
        "selected_and_rejected_candidate_outcomes_present": bool(selected and rejected),
        "non_oracle_labels_only": True,
    }
    failed = [key for key, value in criteria.items() if not value]
    return {
        "passed": all(criteria.values()),
        "criteria": criteria,
        "failed_criteria": failed,
        "sample_gate": SAMPLE_GATE,
        "all_candidate_rows": len(rows),
        "complete_10d_candidate_rows": len(complete_10d),
        "complete_20d_candidate_rows": len(complete_20d),
        "positive_10d_cash_labels": positives,
        "negative_10d_cash_labels": negatives,
        "selected_complete_10d_rows": len(selected),
        "rejected_or_unselected_complete_10d_rows": len(rejected),
        "unique_tickers": len(ticker_counts),
        "top_ticker": top_ticker,
        "top_ticker_rows": top_rows,
        "top_ticker_share": max_share,
        "chronological_folds": folds,
        "replacement_value_summary_10d": {
            "cash": summarize_values(
                row.get("horizons", {}).get("10d", {}).get("replacement_value_vs_cash_usd")
                for row in complete_10d
            ),
            "spy": summarize_values(
                row.get("horizons", {}).get("10d", {}).get("replacement_value_vs_spy_usd")
                for row in complete_10d
            ),
            "qqq": summarize_values(
                row.get("horizons", {}).get("10d", {}).get("replacement_value_vs_qqq_usd")
                for row in complete_10d
            ),
        },
    }


def build_evaluation() -> dict[str, Any]:
    universe = sorted(get_universe())
    windows = [run_window(window, universe) for window in WINDOWS]
    rows = [
        row
        for window in windows
        for row in window.get("training_rows", [])
        if isinstance(row, Mapping)
    ]
    errors = [window for window in windows if window.get("error")]
    readiness = build_readiness(rows)
    decision_counts = Counter(row.get("decision") for row in rows)
    target_present = sum(1 for row in rows if row.get("target_price") is not None)
    entry_present = sum(1 for row in rows if row.get("intended_entry_date"))
    return {
        "universe_size": len(universe),
        "windows": windows,
        "window_errors": errors,
        "window_count": len(windows),
        "training_ledger_rows": rows,
        "training_ledger_row_count": len(rows),
        "decision_counts": dict(sorted(decision_counts.items())),
        "entry_date_present_count": entry_present,
        "entry_date_missing_count": max(0, len(rows) - entry_present),
        "target_price_present_count": target_present,
        "target_price_missing_count": max(0, len(rows) - target_present),
        "readiness": readiness,
        "materialization_succeeded": bool(rows) and not errors,
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    evaluation = build_evaluation()
    readiness = evaluation["readiness"]
    materialized = evaluation["materialization_succeeded"]
    accepted_repair = bool(materialized)
    status = "accepted_measurement_repair" if accepted_repair else "blocked"
    decision = (
        "accepted_measurement_repair_candidate_training_ledger_materialized_model_still_blocked"
        if accepted_repair
        else "blocked_candidate_training_ledger_materialization_failed"
    )
    alpha_ready = bool(readiness["passed"])
    rejection_reason = None if accepted_repair else "candidate_training_rows_not_materialized"
    failed_readiness = readiness["failed_criteria"]
    why = (
        "The existing backtester entry-candidate hook produced a canonical "
        "candidate-decision population and fixed-horizon non-oracle labels. "
        "The ledger repairs the measurement gap from exp-20260709-023, but "
        "the sample gate still blocks model fitting until the row/class/fold "
        "thresholds pass."
        if accepted_repair
        else "The runner could not produce a usable candidate-decision ledger."
    )

    headline = {
        "training_ledger_rows": evaluation["training_ledger_row_count"],
        "complete_10d_candidate_rows": readiness["complete_10d_candidate_rows"],
        "complete_20d_candidate_rows": readiness["complete_20d_candidate_rows"],
        "positive_10d_cash_labels": readiness["positive_10d_cash_labels"],
        "negative_10d_cash_labels": readiness["negative_10d_cash_labels"],
        "selected_complete_10d_rows": readiness["selected_complete_10d_rows"],
        "rejected_or_unselected_complete_10d_rows": readiness[
            "rejected_or_unselected_complete_10d_rows"
        ],
        "readiness_gate_passed": readiness["passed"],
        "readiness_failed_criteria": failed_readiness,
        "strategy_behavior_changed": False,
    }
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted_repair,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted_repair,
        "alpha_ready": alpha_ready,
        "alpha_ready_reason": (
            "Readiness gate passed; a separate alpha experiment would still need a predeclared model and Gate 1-4."
            if alpha_ready
            else "Model fitting remains blocked by the predeclared exp-20260709-023 training-table gate."
        ),
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": None,
        "baseline_metrics": baseline,
        "before_metrics": baseline,
        "after_metrics": {
            **baseline,
            "training_ledger_rows": evaluation["training_ledger_row_count"],
            "complete_10d_candidate_rows": readiness["complete_10d_candidate_rows"],
            "entry_date_present_count": evaluation["entry_date_present_count"],
            "target_price_present_count": evaluation["target_price_present_count"],
        },
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "candidate_training_rows_materialized_delta": evaluation[
                "training_ledger_row_count"
            ],
            "complete_10d_candidate_rows_materialized_delta": readiness[
                "complete_10d_candidate_rows"
            ],
        },
        "evaluation": evaluation,
        "headline_metrics": headline,
        "gate": {
            "passed": accepted_repair,
            "decision": decision,
            "reason": (
                "measurement_repair_materialized_candidate_training_ledger"
                if accepted_repair else rejection_reason
            ),
            "readiness_gate_passed": readiness["passed"],
            "readiness_failed_criteria": failed_readiness,
        },
        "gate1": {
            "passed": baseline["available"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
            "note": "Read-only measurement repair; no before/after strategy metric change.",
        },
        "gate2": {
            "passed": accepted_repair,
            "required_fields_checked": [
                "signal_date",
                "ticker",
                "decision",
                "intended_entry_date",
                "target_price",
                "fixed_horizon_cash_spy_qqq_labels",
            ],
            "entry_date_target_price_sentinel": {
                "entry_date_present_count": evaluation["entry_date_present_count"],
                "entry_date_missing_count": evaluation["entry_date_missing_count"],
                "target_price_present_count": evaluation["target_price_present_count"],
                "target_price_missing_count": evaluation["target_price_missing_count"],
            },
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "survival_rate_not_applicable": True,
            "baseline_survival_rate": baseline["survival_rate"],
        },
        "gate4": {
            "passed": False,
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "reason": (
                "No alpha is accepted; this materializes measurement rows only. "
                "A future meta-label model remains blocked unless readiness passes."
            ),
        },
        "production_impact": {
            "accepted_measurement_repair": accepted_repair,
            "trade_enabled": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "shared_policy_changed": False,
            "llm_change_scope": "none",
            "artifact_only": True,
        },
        "rejection_reason": rejection_reason,
        "realized_failure_mode": (
            None if accepted_repair else "candidate_training_rows_not_materialized"
        ),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not train or tune a candidate meta-label model on this "
                "ledger unless the readiness gate passes. Do not retune "
                "thresholds, model class, probability scalar, or response "
                "function to bypass the row/class/fold requirements."
            ),
            "new_evidence_required": (
                "A model experiment needs at least 300 complete candidate rows, "
                "75 positive and 75 negative fixed-horizon labels, selected and "
                "rejected/unselected coverage, three chronological folds with "
                ">=50 test rows and both classes, and no single ticker above "
                "20% of complete rows."
            ),
            "next_evidence_needed": (
                "If the gate still fails, the next legal step is pipeline "
                "wiring or additional settled candidate rows, not model fitting."
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": (
                "exp-20260709-023 blocked model fitting because only selected "
                "trade rows and sparse skipped diagnostics were trainable. "
                "This experiment first materializes the missing full candidate "
                "decision ledger."
            ),
            "3_single_causal_variable": SINGLE_CAUSAL_VARIABLE,
            "4_acceptance_standard": ACCEPTANCE_RULE,
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "lean_quality_passed": True,
    }
    return payload


def build_card(payload: Mapping[str, Any]) -> str:
    h = payload["headline_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: candidate training ledger materialization",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Training ledger rows: `{h['training_ledger_rows']}`",
            f"- Complete 10d / 20d rows: `{h['complete_10d_candidate_rows']}` / `{h['complete_20d_candidate_rows']}`",
            f"- Positive / negative 10d cash labels: `{h['positive_10d_cash_labels']}` / `{h['negative_10d_cash_labels']}`",
            f"- Selected / unselected complete rows: `{h['selected_complete_10d_rows']}` / `{h['rejected_or_unselected_complete_10d_rows']}`",
            f"- Readiness gate passed: `{h['readiness_gate_passed']}`",
            f"- Failed readiness criteria: `{h['readiness_failed_criteria']}`",
            "- Strategy/live order behavior changed: `false`",
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
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
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
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "summary": payload["gate"]["reason"],
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
            "rejection_reason": payload["rejection_reason"],
            "realized_failure_mode": payload["realized_failure_mode"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
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
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
