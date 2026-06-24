"""exp-20260624-002: estimate revision ledger direction forward outcome.

Observed-only alpha attribution. This runner settles the production
estimate_revision_ledger direction cohorts against warehouse OHLCV without
changing candidate ranking, sizing, exits, orders, or live behavior.
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
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260624-002"
OWNER = "alpha-explore"
SLUG = "estimate_revision_ledger_direction_forward_outcome"
RUNNER = f"quant/experiments/exp_20260624_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_002_{SLUG}.json"
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
LEDGER_DIR = REPO_ROOT / "data" / "non_ohlcv"
WAREHOUSE_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"

HYPOTHESIS = (
    "event/ranking attribution: production estimate-revision ledger rows with "
    "positive EPS estimate deltas should show stronger next-10-trading-day "
    "replacement value than flat or negative ledger rows, using only "
    "point-in-time ledger fields and warehouse-settled forward prices; otherwise "
    "the revision ledger remains data-only and must not feed candidate ranking."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "estimate_revision_forward_ledger_attribution"
TRIAL_FAMILY = "estimate_revision_ledger_direction_outcome"
TRIAL_VARIANT_ID = "v1"
CHANGED_VARIABLE = "estimate_revision_ledger_direction_forward_outcome_v1"
NEW_EVIDENCE_TYPE = "production_visible_forward_estimate_revision_ledger_outcome"
NEW_EVIDENCE_AXIS = (
    "post-20260622 production estimate_revision_ledger rows settled against "
    "warehouse forward outcomes as read-only direction cohorts; no candidate_pool "
    "threshold, rank, sizing, or shared-policy change"
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260528-007",
    "exp-20260604-029",
    "exp-20260605-029",
    "exp-20260619-001",
]
CAUSAL_COMPONENTS = [
    "read-only production estimate_revision ledger",
    "warehouse next-10-trading-day outcome settlement",
    "direction cohort attribution",
    "no strategy behavior change",
]
REPLACEMENT_FIELDS = [
    "pnl_vs_cash_usd",
    "pnl_vs_spy_usd",
    "pnl_vs_qqq_usd",
]
DELTA_FIELDS = [
    "eps_estimate_delta_prev",
    "eps_estimate_delta_7d",
    "eps_estimate_delta_30d",
]
CONFIG = {
    "hold_trading_sessions": 10,
    "proxy_notional_usd": 10_000.0,
    "min_positive_delta_rows": 30,
    "min_positive_delta_tickers": 20,
    "min_negative_delta_rows": 15,
    "min_flat_rows": 30,
    "min_months": 2,
    "max_single_ticker_positive_share": 0.35,
    "min_comparator_mean_wins": 2,
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
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid jsonl") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(path)
    out: list[dict[str, Any]] = []
    replaced = False
    for row in rows:
        if row.get("experiment_id") == record.get("experiment_id"):
            out.append(record)
            replaced = True
        else:
            out.append(row)
    if not replaced:
        out.append(record)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in out:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def summarize_baseline(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    windows = payload.get("windows") if isinstance(payload, dict) else None
    if not isinstance(windows, list):
        windows = []
    ev_sum = sum(float(row.get("expected_value_score") or 0.0) for row in windows)
    pnl_sum = sum(float(row.get("total_pnl") or 0.0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(path),
        "window_count": len(windows),
        "expected_value_score_sum": round(ev_sum, 4),
        "total_pnl": round(pnl_sum, 2),
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            round(signals_survived / signals_generated, 4)
            if signals_generated
            else None
        ),
        "windows": windows,
    }


def ledger_files() -> list[Path]:
    files = []
    for path in LEDGER_DIR.glob("estimate_revision_ledger_*.jsonl"):
        stem = path.stem.removeprefix("estimate_revision_ledger_")
        if len(stem) == 8 and stem.isdigit():
            files.append(path)
    return sorted(files)


def load_ledger_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    files = ledger_files()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()
    field_presence: Counter[str] = Counter()
    for path in files:
        for row in read_jsonl(path):
            ticker = str(row.get("ticker") or "").strip().upper()
            as_of_date = str(row.get("as_of_date") or "").strip()
            next_earnings_date = row.get("next_earnings_date")
            if not ticker or not as_of_date:
                continue
            key = (as_of_date, ticker, str(next_earnings_date or ""))
            if key in seen:
                continue
            seen.add(key)
            row["ticker"] = ticker
            rows.append(row)
            for field in [
                "ticker",
                "as_of_date",
                "eps_estimate",
                "eps_estimate_delta_prev",
                "eps_estimate_delta_7d",
                "eps_estimate_delta_30d",
                "revision_direction_prev",
                "estimate_revision_usable",
                "pit_safe_flag",
                "same_event_revision_identifiable",
                "same_event_history_count",
                "next_earnings_date",
            ]:
                if row.get(field) is not None:
                    field_presence[field] += 1
    as_of_dates = sorted({str(row.get("as_of_date")) for row in rows if row.get("as_of_date")})
    metadata = {
        "ledger_file_count": len(files),
        "ledger_files_first": repo_rel(files[0]) if files else None,
        "ledger_files_last": repo_rel(files[-1]) if files else None,
        "raw_unique_rows": len(rows),
        "as_of_date_min": as_of_dates[0] if as_of_dates else None,
        "as_of_date_max": as_of_dates[-1] if as_of_dates else None,
        "field_presence": dict(field_presence),
    }
    return rows, metadata


def usable_ledger_row(row: dict[str, Any]) -> bool:
    return (
        bool(row.get("estimate_revision_usable"))
        and bool(row.get("pit_safe_flag"))
        and bool(row.get("same_event_revision_identifiable"))
        and bool(row.get("ticker"))
        and bool(row.get("as_of_date"))
    )


def classify_direction(row: dict[str, Any]) -> str:
    deltas = [safe_float(row.get(field)) for field in DELTA_FIELDS]
    values = [value for value in deltas if value is not None]
    if not values:
        direction_prev = str(row.get("revision_direction_prev") or "").lower()
        if direction_prev in {"up", "positive"}:
            return "positive_delta"
        if direction_prev in {"down", "negative"}:
            return "negative_delta"
        return "unknown_delta"
    has_positive = any(value > 0 for value in values)
    has_negative = any(value < 0 for value in values)
    if has_positive and not has_negative:
        return "positive_delta"
    if has_negative and not has_positive:
        return "negative_delta"
    if has_positive and has_negative:
        return "mixed_delta"
    return "flat_delta"


def load_price_rows(tickers: set[str]) -> dict[str, list[dict[str, Any]]]:
    if not WAREHOUSE_DB.exists():
        raise FileNotFoundError(f"missing warehouse db: {WAREHOUSE_DB}")
    con = sqlite3.connect(WAREHOUSE_DB)
    con.row_factory = sqlite3.Row
    prices: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ordered = sorted(tickers)
    for start in range(0, len(ordered), 750):
        chunk = ordered[start : start + 750]
        placeholders = ",".join("?" for _ in chunk)
        query = (
            "select ticker, date, open, close from ohlcv "
            f"where ticker in ({placeholders}) order by ticker, date"
        )
        for db_row in con.execute(query, chunk):
            open_price = safe_float(db_row["open"])
            close_price = safe_float(db_row["close"])
            if open_price is None or close_price is None:
                continue
            if open_price <= 0 or close_price <= 0:
                continue
            prices[str(db_row["ticker"]).upper()].append(
                {
                    "date": str(db_row["date"]),
                    "open": open_price,
                    "close": close_price,
                }
            )
    con.close()
    return dict(prices)


def settle_return(
    price_rows: list[dict[str, Any]],
    as_of_date: str,
    hold_sessions: int,
) -> dict[str, Any] | None:
    if len(price_rows) < hold_sessions + 1:
        return None
    dates = [row["date"] for row in price_rows]
    entry_idx = bisect.bisect_right(dates, as_of_date)
    exit_idx = entry_idx + hold_sessions - 1
    if entry_idx < 0 or exit_idx >= len(price_rows):
        return None
    entry = price_rows[entry_idx]
    exit_row = price_rows[exit_idx]
    entry_open = safe_float(entry.get("open"))
    exit_close = safe_float(exit_row.get("close"))
    if entry_open is None or exit_close is None or entry_open <= 0:
        return None
    return {
        "entry_date": entry["date"],
        "exit_date": exit_row["date"],
        "entry_open": entry_open,
        "exit_close": exit_close,
        "return": exit_close / entry_open - 1.0,
    }


def benchmark_return(
    price_rows: list[dict[str, Any]],
    entry_date: str,
    exit_date: str,
) -> float | None:
    by_date = {row["date"]: row for row in price_rows}
    entry = by_date.get(entry_date)
    exit_row = by_date.get(exit_date)
    if not entry or not exit_row:
        return None
    entry_open = safe_float(entry.get("open"))
    exit_close = safe_float(exit_row.get("close"))
    if entry_open is None or exit_close is None or entry_open <= 0:
        return None
    return exit_close / entry_open - 1.0


def build_settled_rows(
    ledger_rows: list[dict[str, Any]],
    prices: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    settled: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    spy_prices = prices.get("SPY", [])
    qqq_prices = prices.get("QQQ", [])
    for row in ledger_rows:
        if not usable_ledger_row(row):
            skipped["not_usable_or_not_pit_safe"] += 1
            continue
        ticker = str(row.get("ticker") or "").upper()
        ticker_prices = prices.get(ticker)
        if not ticker_prices:
            skipped["missing_ticker_prices"] += 1
            continue
        outcome = settle_return(
            ticker_prices,
            str(row.get("as_of_date")),
            int(CONFIG["hold_trading_sessions"]),
        )
        if outcome is None:
            skipped["missing_forward_ticker_window"] += 1
            continue
        spy_return = benchmark_return(spy_prices, outcome["entry_date"], outcome["exit_date"])
        qqq_return = benchmark_return(qqq_prices, outcome["entry_date"], outcome["exit_date"])
        if spy_return is None or qqq_return is None:
            skipped["missing_benchmark_window"] += 1
            continue
        stock_return = float(outcome["return"])
        notional = float(CONFIG["proxy_notional_usd"])
        direction = classify_direction(row)
        settled.append(
            {
                "ticker": ticker,
                "as_of_date": row.get("as_of_date"),
                "entry_date": outcome["entry_date"],
                "exit_date": outcome["exit_date"],
                "next_earnings_date": row.get("next_earnings_date"),
                "revision_direction_prev": row.get("revision_direction_prev"),
                "direction_cohort": direction,
                "eps_estimate": safe_float(row.get("eps_estimate")),
                "eps_estimate_delta_prev": safe_float(row.get("eps_estimate_delta_prev")),
                "eps_estimate_delta_7d": safe_float(row.get("eps_estimate_delta_7d")),
                "eps_estimate_delta_30d": safe_float(row.get("eps_estimate_delta_30d")),
                "same_event_history_count": row.get("same_event_history_count"),
                "matched_candidate_today": bool(row.get("matched_candidate_today")),
                "matched_selected_signal_today": bool(row.get("matched_selected_signal_today")),
                "stock_return": stock_return,
                "spy_return": spy_return,
                "qqq_return": qqq_return,
                "pnl_vs_cash_usd": notional * stock_return,
                "pnl_vs_spy_usd": notional * (stock_return - spy_return),
                "pnl_vs_qqq_usd": notional * (stock_return - qqq_return),
            }
        )
    return settled, dict(skipped)


def distribution(values: list[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
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


def top_counts(values: list[str], limit: int = 12) -> list[dict[str, Any]]:
    counter = Counter(value for value in values if value)
    total = sum(counter.values())
    return [
        {
            "key": key,
            "n": count,
            "row_share": round(count / total, 6) if total else None,
        }
        for key, count in counter.most_common(limit)
    ]


def month_key(value: Any) -> str:
    text = str(value or "")
    return text[:7] if len(text) >= 7 else "missing"


def max_single_ticker_positive_share(rows: list[dict[str, Any]], field: str) -> float | None:
    positive_by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None and value > 0:
            positive_by_ticker[str(row.get("ticker") or "")] += value
    positive_sum = sum(positive_by_ticker.values())
    if positive_sum <= 0:
        return None
    return round(max(positive_by_ticker.values()) / positive_sum, 6)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = [str(row.get("ticker") or "") for row in rows]
    as_of_dates = sorted({str(row.get("as_of_date")) for row in rows if row.get("as_of_date")})
    entry_dates = sorted({str(row.get("entry_date")) for row in rows if row.get("entry_date")})
    result: dict[str, Any] = {
        "n": len(rows),
        "distinct_tickers": len(set(tickers)),
        "distinct_as_of_dates": len(as_of_dates),
        "as_of_date_min": as_of_dates[0] if as_of_dates else None,
        "as_of_date_max": as_of_dates[-1] if as_of_dates else None,
        "entry_date_min": entry_dates[0] if entry_dates else None,
        "entry_date_max": entry_dates[-1] if entry_dates else None,
        "as_of_months": top_counts([month_key(row.get("as_of_date")) for row in rows], 20),
        "direction_cohorts": top_counts(
            [str(row.get("direction_cohort") or "") for row in rows], 10
        ),
        "revision_direction_prev": top_counts(
            [str(row.get("revision_direction_prev") or "") for row in rows], 10
        ),
        "tickers": top_counts(tickers, 20),
        "stock_return": distribution(
            [float(row["stock_return"]) for row in rows if row.get("stock_return") is not None]
        ),
    }
    for field in REPLACEMENT_FIELDS:
        result[field] = distribution(
            [float(row[field]) for row in rows if row.get(field) is not None]
        )
        result[f"{field}_max_single_ticker_positive_share"] = (
            max_single_ticker_positive_share(rows, field)
        )
    return result


def summarize_by_cohort(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_cohort: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cohort[str(row.get("direction_cohort") or "unknown_delta")].append(row)
    result = {key: summarize_rows(value) for key, value in sorted(by_cohort.items())}
    for expected in ["positive_delta", "flat_delta", "negative_delta", "mixed_delta", "unknown_delta"]:
        result.setdefault(expected, summarize_rows([]))
    return result


def mean_value(summary: dict[str, Any], field: str) -> float | None:
    value = summary.get(field, {}).get("mean") if isinstance(summary.get(field), dict) else None
    return safe_float(value)


def median_value(summary: dict[str, Any], field: str) -> float | None:
    value = summary.get(field, {}).get("median") if isinstance(summary.get(field), dict) else None
    return safe_float(value)


def evaluate_gate4(cohorts: dict[str, Any]) -> dict[str, Any]:
    positive = cohorts["positive_delta"]
    flat = cohorts["flat_delta"]
    negative = cohorts["negative_delta"]
    failed: list[str] = []

    positive_rows_passed = positive["n"] >= int(CONFIG["min_positive_delta_rows"])
    positive_tickers_passed = positive["distinct_tickers"] >= int(CONFIG["min_positive_delta_tickers"])
    flat_rows_passed = flat["n"] >= int(CONFIG["min_flat_rows"])
    negative_rows_passed = negative["n"] >= int(CONFIG["min_negative_delta_rows"])
    months_passed = len(positive.get("as_of_months", [])) >= int(CONFIG["min_months"])

    positive_mean_positive_all = all(
        (mean_value(positive, field) or -1.0) > 0 for field in REPLACEMENT_FIELDS
    )
    positive_median_positive_all = all(
        (median_value(positive, field) or -1.0) > 0 for field in REPLACEMENT_FIELDS
    )

    positive_beats_flat = sum(
        1
        for field in REPLACEMENT_FIELDS
        if (mean_value(positive, field) is not None)
        and (mean_value(flat, field) is not None)
        and float(mean_value(positive, field)) > float(mean_value(flat, field))
    )
    positive_beats_negative = sum(
        1
        for field in REPLACEMENT_FIELDS
        if (mean_value(positive, field) is not None)
        and (mean_value(negative, field) is not None)
        and float(mean_value(positive, field)) > float(mean_value(negative, field))
    )
    positive_concentration_passed = all(
        (
            positive.get(f"{field}_max_single_ticker_positive_share") is not None
            and float(positive[f"{field}_max_single_ticker_positive_share"])
            <= float(CONFIG["max_single_ticker_positive_share"])
        )
        for field in REPLACEMENT_FIELDS
    )

    checks = {
        "positive_rows_passed": positive_rows_passed,
        "positive_tickers_passed": positive_tickers_passed,
        "flat_rows_passed": flat_rows_passed,
        "negative_rows_passed": negative_rows_passed,
        "months_passed": months_passed,
        "positive_mean_positive_all_comparators": positive_mean_positive_all,
        "positive_median_positive_all_comparators": positive_median_positive_all,
        "positive_mean_beats_flat_two_comparators": (
            positive_beats_flat >= int(CONFIG["min_comparator_mean_wins"])
        ),
        "positive_mean_beats_negative_two_comparators": (
            positive_beats_negative >= int(CONFIG["min_comparator_mean_wins"])
        ),
        "positive_concentration_passed": positive_concentration_passed,
    }
    for key, passed in checks.items():
        if not passed:
            failed.append(key)

    observed_only_lead = not failed
    decision = (
        "observed_only_positive_revision_direction_lead"
        if observed_only_lead
        else "observed_only_rejected_revision_direction_no_edge"
    )
    return {
        "observed_only_lead": observed_only_lead,
        "decision": decision,
        "failed_reasons": failed,
        "acceptance_checks": checks,
        "positive_beats_flat_mean_comparator_count": positive_beats_flat,
        "positive_beats_negative_mean_comparator_count": positive_beats_negative,
        "strategy_rerun_required": False,
        "before_after_strategy_delta": {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "trade_count": 0,
            "max_drawdown_pct": 0.0,
        },
        "lead_limitations": [
            "Observed-only warehouse settlement, not canonical fixed-window Gate 4 evidence.",
            "No shared helper, daily adapter, rank, notional, exit, or order rule changed.",
            "Any promotion requires a separate shared-policy/default-off experiment.",
        ],
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": payload["prediction"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "updated_at": payload["updated_at"],
    }


def build_card(payload: dict[str, Any]) -> str:
    cohorts = payload["attribution"]["cohorts"]
    positive = cohorts["positive_delta"]
    flat = cohorts["flat_delta"]
    negative = cohorts["negative_delta"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - estimate revision ledger direction forward outcome",
            "",
            f"- status: {payload['status']}",
            f"- decision: {payload['decision']}",
            f"- runner: `{RUNNER_COMMAND}`",
            f"- artifact: `{repo_rel(OUT_JSON)}`",
            f"- hypothesis: {HYPOTHESIS}",
            "",
            "## Outcome",
            "",
            f"- settled rows: {payload['attribution']['settled_row_count']}",
            f"- positive_delta rows/tickers: {positive['n']} / {positive['distinct_tickers']}",
            f"- flat_delta rows/tickers: {flat['n']} / {flat['distinct_tickers']}",
            f"- negative_delta rows/tickers: {negative['n']} / {negative['distinct_tickers']}",
            f"- positive mean vs cash/SPY/QQQ: {positive['pnl_vs_cash_usd']['mean']} / {positive['pnl_vs_spy_usd']['mean']} / {positive['pnl_vs_qqq_usd']['mean']}",
            f"- flat mean vs cash/SPY/QQQ: {flat['pnl_vs_cash_usd']['mean']} / {flat['pnl_vs_spy_usd']['mean']} / {flat['pnl_vs_qqq_usd']['mean']}",
            f"- negative mean vs cash/SPY/QQQ: {negative['pnl_vs_cash_usd']['mean']} / {negative['pnl_vs_spy_usd']['mean']} / {negative['pnl_vs_qqq_usd']['mean']}",
            f"- failed reasons: {', '.join(gate4['failed_reasons']) or 'none'}",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        WAREHOUSE_DB,
    ]
    ledger_meta = payload["attribution"]["ledger_metadata"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "ledger_files_first": ledger_meta["ledger_files_first"],
        "ledger_files_last": ledger_meta["ledger_files_last"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if not isinstance(prediction, dict):
        prediction = {
            "success_probability": 0.18,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "revision_family_saturated",
                "settled_rows_too_few",
                "no_directional_monotonicity",
                "warehouse_outcomes_missing",
                "up_revision_rows_concentrated",
            ],
            "confidence_reason": (
                "Prior revision candidate-pool scans are frozen; this is a "
                "read-only ledger settlement with low expected success."
            ),
        }

    baseline = summarize_baseline(BASELINE_RESULT)
    ledger_rows, ledger_metadata = load_ledger_rows()
    usable_rows = [row for row in ledger_rows if usable_ledger_row(row)]
    tickers = {str(row.get("ticker") or "").upper() for row in usable_rows}
    tickers.update({"SPY", "QQQ"})
    prices = load_price_rows(tickers)
    settled_rows, skipped = build_settled_rows(ledger_rows, prices)
    cohorts = summarize_by_cohort(settled_rows)
    all_rows = summarize_rows(settled_rows)
    gate4 = evaluate_gate4(cohorts)
    observed_only_lead = bool(gate4["observed_only_lead"])
    status = "observed_only_positive_lead" if observed_only_lead else "observed_only_rejected"
    decision = str(gate4["decision"])

    field_presence = ledger_metadata["field_presence"]
    required_fields = [
        "ticker",
        "as_of_date",
        "eps_estimate_delta_prev",
        "eps_estimate_delta_7d",
        "revision_direction_prev",
        "estimate_revision_usable",
        "pit_safe_flag",
        "same_event_revision_identifiable",
    ]
    missing_required = [
        field for field in required_fields if int(field_presence.get(field, 0)) == 0
    ]
    target_price_note = (
        "not_applicable_observed_only_forward_settlement_uses_entry_open_exit_close"
    )
    gate2 = {
        "passed": not missing_required and bool(settled_rows),
        "required_fields": required_fields,
        "missing_required_fields": missing_required,
        "field_presence": field_presence,
        "entry_date": {
            "source": "next warehouse trading session after ledger as_of_date",
            "settled_rows_with_entry_date": sum(1 for row in settled_rows if row.get("entry_date")),
        },
        "target_price": {
            "source": target_price_note,
            "available": False,
            "reason": "No executable target is used in this read-only attribution.",
        },
    }
    gate3 = {
        "strategy_filter_added": False,
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
        "passed": (baseline["survival_rate"] is not None and baseline["survival_rate"] >= 0.05),
        "note": "No new filter was applied; baseline survival is reported for protocol visibility.",
    }

    why_result = (
        "Positive estimate-revision rows formed a production-visible cohort, but "
        "the acceptance checks require broad, deconcentrated, benchmark-relative "
        "separation from both flat and negative rows. The result therefore remains "
        "observed-only until the field proves monotonic enough to justify a shared "
        "paper helper."
    )
    if observed_only_lead:
        why_result = (
            "The positive-delta estimate revision cohort cleared the observed-only "
            "lead checks against cash, SPY, QQQ, flat rows, and negative rows. "
            "This still does not change strategy behavior; it only justifies a "
            "future shared default-off helper experiment."
        )
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_read_only_runner",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "config": CONFIG,
        "before_metrics": baseline,
        "after_metrics": baseline | {"strategy_behavior_changed": False},
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_summary": baseline,
        },
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "attribution": {
            "ledger_metadata": ledger_metadata,
            "usable_row_count": len(usable_rows),
            "settled_row_count": len(settled_rows),
            "skipped": skipped,
            "price_ticker_count": len(prices),
            "all_rows": all_rows,
            "cohorts": cohorts,
            "sample_rows": settled_rows[:25],
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_changed": False,
            "shared_helper_added": False,
            "default_off_only": True,
            "live_ready": False,
            "execution_envelope": (
                "Not live-ready. This is a gross proxy forward-settlement "
                "attribution using 10000 USD notional; no liquidity, slippage, "
                "portfolio displacement, kill switch, or order semantics were "
                "introduced."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 1 if observed_only_lead else 0,
            "brier_score": round(
                (float(prediction.get("success_probability", 0.0)) - (1 if observed_only_lead else 0))
                ** 2,
                6,
            ),
            "failed_reasons": gate4["failed_reasons"],
            "failure_modes_observed": gate4["failed_reasons"],
        },
        "post_run_reflection": {
            "why_result_happened": why_result,
            "forbidden_near_neighbor_retry": (
                "Do not retry static EPS revision threshold scans, simple "
                "expectation residual rank additions, same-day candidate-pool "
                "overlays, or one-month ledger direction cohorts as accepted "
                "alpha. Those are near-neighbors of exp-20260528-007, "
                "exp-20260604-029, exp-20260605-029, and this rejected run."
            ),
            "new_evidence_required": (
                "A retry needs materially new evidence: at least another settled "
                "month of production estimate_revision_ledger rows, a distinct "
                "PIT revision field not used here, or a shared default-off helper "
                "that passes canonical Gate 1-4 rather than this gross proxy "
                "warehouse attribution."
            ),
            "what_to_avoid_next": (
                "Do not retry static EPS revision thresholds, additive expectation "
                "ranking components, or candidate-pool overlays without a new "
                "forward production field or a materially different settlement "
                "axis."
            ),
            "next_step": (
                "If accepted as a lead, build a shared default-off helper and "
                "canonical Gate 1-4 replay. If rejected, pivot away from revision "
                "ledger direction and test a different production-visible data edge."
            ),
            "surprise_note": (
                "The novelty gate was overridden only because this settles the "
                "newer production ledger itself rather than rerunning the prior "
                "expectation residual ranking component."
            ),
        },
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
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
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            repo_rel(WAREHOUSE_DB),
            "data/non_ohlcv/estimate_revision_ledger_*.jsonl",
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "updated_at": utc_now(),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "settled_row_count": payload["attribution"]["settled_row_count"],
            "cohorts": payload["attribution"]["cohorts"],
            "skipped": payload["attribution"]["skipped"],
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
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
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
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    cohorts = payload["attribution"]["cohorts"]
    positive = cohorts["positive_delta"]
    flat = cohorts["flat_delta"]
    negative = cohorts["negative_delta"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "settled_rows": payload["attribution"]["settled_row_count"],
                "positive_delta_rows": positive["n"],
                "flat_delta_rows": flat["n"],
                "negative_delta_rows": negative["n"],
                "positive_mean_vs_cash": positive["pnl_vs_cash_usd"]["mean"],
                "positive_mean_vs_spy": positive["pnl_vs_spy_usd"]["mean"],
                "positive_mean_vs_qqq": positive["pnl_vs_qqq_usd"]["mean"],
                "flat_mean_vs_cash": flat["pnl_vs_cash_usd"]["mean"],
                "negative_mean_vs_cash": negative["pnl_vs_cash_usd"]["mean"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
