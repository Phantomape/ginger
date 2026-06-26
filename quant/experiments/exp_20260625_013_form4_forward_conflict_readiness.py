"""exp-20260625-013: Form 4 forward replacement conflict readiness.

Observed-only alpha attribution. This runner tests the machine-checkable
evidence axis recorded in the reservation: current daily Form 4 transaction XML
rows joined to canonical closed forward replacement rows. It does not alter any
strategy helper, candidate ranking, sizing, entry, exit, paper order, live order,
or daily sleeve artifact.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-013"
OWNER = "alpha-explore"
SLUG = "form4_forward_conflict_readiness"
RUNNER = f"quant/experiments/exp_20260625_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_013_{SLUG}.json"
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
FORWARD_REPLACEMENT = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
FORM4_TRANSACTIONS = REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20260624.jsonl"

HYPOTHESIS = (
    "Observed-only alpha hypothesis: current PIT Form 4 sale pressure and "
    "post-sale retention context can identify accepted/default-off paper rows "
    "whose forward replacement value is weaker; first test whether daily Form 4 "
    "transactions join to canonical closed forward replacement rows with enough "
    "sample and direction."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
TRIAL_FAMILY = "form4_forward_replacement_context_attribution"
TRIAL_VARIANT_ID = "current_20260624_transaction_join_v1"
CHANGED_VARIABLE = "form4_daily_sale_pressure_forward_replacement_context_v1"
NEW_EVIDENCE_TYPE = "daily_form4_forward_replacement_join"
NEW_EVIDENCE_AXIS = (
    "Non-scan forward replacement join: current 2026-06-24 daily Form4 "
    "transaction XML fields are joined to canonical closed "
    "forward_replacement_value rows with PIT ticker/date windows; not a "
    "frozen-window Form4 candidate pool, threshold, hold-day, source-rank, or "
    "notional sweep."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260616-012",
    "exp-20260616-013",
    "exp-20260623-024",
    "exp-20260624-008",
]
CAUSAL_COMPONENTS = [
    "daily Form4 transaction XML fields",
    "canonical forward_replacement_value closed rows",
    "ticker/date-window attribution",
    "no strategy behavior change",
]
REPLACEMENT_FIELDS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONFIG = {
    "lookback_days_before_entry": 3,
    "min_any_form4_rows": 8,
    "min_sale_pressure_rows": 6,
    "min_sale_pressure_tickers": 2,
    "max_single_ticker_sale_pressure_share": 0.60,
    "min_underperform_mean_fields": 2,
    "min_underperform_median_fields": 2,
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
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
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
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != record["experiment_id"]:
                kept.append(json.dumps(existing, sort_keys=True))
    kept.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_date(value: Any) -> date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def counter_dict(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): int(value) for key, value in counter.most_common()}


def row_identity(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("decision_id") or ""),
        str(row.get("ticker") or ""),
        str(row.get("entry_date") or ""),
        str(row.get("exit_date") or ""),
        str(row.get("sleeve_key") or ""),
        str(row.get("asof_date") or ""),
    ]
    return "|".join(parts)


def form4_identity(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("accession_number") or ""),
        str(row.get("owner_cik") or ""),
        str(row.get("ticker") or row.get("issuer_trading_symbol") or ""),
        str(row.get("transaction_date") or ""),
        str(row.get("transaction_code") or ""),
        str(row.get("shares") or ""),
        str(row.get("price") or ""),
        str(row.get("shares_owned_following_transaction") or ""),
    ]
    return "|".join(parts)


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction:
        return prediction
    return {
        "success_probability": 0.18,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "form4_forward_overlap_too_thin",
            "source_family_saturation",
            "no_replacement_separation",
            "compensation_plumbing_dominates",
        ],
        "confidence_reason": (
            "Fallback prediction from the reserved ticket: Form4 source families "
            "are saturated and the forward replacement ledger is thin."
        ),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
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
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def load_forward_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = read_jsonl(FORWARD_REPLACEMENT)
    deduped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        deduped[row_identity(row)] = row

    usable: list[dict[str, Any]] = []
    missing_required = 0
    for row in deduped.values():
        entry = as_date(row.get("entry_date"))
        exit_ = as_date(row.get("exit_date"))
        ticker = str(row.get("ticker") or "").upper()
        sleeve_key = str(row.get("sleeve_key") or "")
        values = {field: as_float(row.get(field)) for field in REPLACEMENT_FIELDS}
        if (
            entry is None
            or exit_ is None
            or not ticker
            or not sleeve_key
            or any(value is None for value in values.values())
        ):
            missing_required += 1
            continue
        usable.append(
            {
                **row,
                **values,
                "entry_date": entry.isoformat(),
                "exit_date": exit_.isoformat(),
                "entry_date_obj": entry,
                "exit_date_obj": exit_,
                "ticker": ticker,
                "sleeve_key": sleeve_key,
            }
        )
    usable.sort(key=lambda row: (row["entry_date"], row["exit_date"], row["ticker"], row["sleeve_key"]))
    audit = {
        "source_artifact": repo_rel(FORWARD_REPLACEMENT),
        "raw_rows": len(raw_rows),
        "deduped_rows": len(deduped),
        "usable_rows": len(usable),
        "missing_required_rows": missing_required,
        "entry_date_min": min((row["entry_date"] for row in usable), default=None),
        "entry_date_max": max((row["entry_date"] for row in usable), default=None),
        "exit_date_min": min((row["exit_date"] for row in usable), default=None),
        "exit_date_max": max((row["exit_date"] for row in usable), default=None),
        "distinct_tickers": len({row["ticker"] for row in usable}),
        "artifact_not_mutated": True,
    }
    return usable, audit


def normalize_form4(row: dict[str, Any]) -> dict[str, Any] | None:
    usable = as_date(row.get("usable_trade_date"))
    ticker = str(row.get("ticker") or row.get("issuer_trading_symbol") or "").upper()
    code = str(row.get("transaction_code") or "").upper()
    if usable is None or not ticker or not code:
        return None
    shares = as_float(row.get("shares")) or 0.0
    value = as_float(row.get("transaction_value"))
    if value is None:
        price = as_float(row.get("price")) or 0.0
        value = shares * price if shares and price else 0.0
    following = as_float(row.get("shares_owned_following_transaction"))
    retention = None
    if code == "S" and following is not None and shares > 0:
        retention = following / (following + shares) if (following + shares) > 0 else None
    return {
        "ticker": ticker,
        "usable_trade_date": usable.isoformat(),
        "usable_trade_date_obj": usable,
        "transaction_date": str(row.get("transaction_date") or "")[:10] or None,
        "filing_date": str(row.get("filing_date") or "")[:10] or None,
        "accepted_at": row.get("accepted_at"),
        "transaction_code": code,
        "acquired_disposed_code": str(row.get("acquired_disposed_code") or "").upper(),
        "shares": shares,
        "transaction_value": float(value or 0.0),
        "shares_owned_following_transaction": following,
        "post_sale_retention_fraction": retention,
        "10b5_1_flag": bool(row.get("10b5_1_flag")),
        "open_market_purchase_flag": bool(row.get("open_market_purchase_flag")),
        "option_exercise_flag": bool(row.get("option_exercise_flag")),
        "is_officer": bool(row.get("is_officer")),
        "is_director": bool(row.get("is_director")),
        "is_10pct_owner": bool(row.get("is_10pct_owner")),
        "owner_name": row.get("owner_name"),
        "owner_cik": row.get("owner_cik"),
        "officer_title": row.get("officer_title"),
        "accession_number": row.get("accession_number"),
        "pit_safe_flag": bool(row.get("pit_safe_flag")),
        "source": row.get("source"),
    }


def load_form4_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = read_jsonl(FORM4_TRANSACTIONS)
    deduped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        deduped[form4_identity(row)] = row

    usable: list[dict[str, Any]] = []
    missing_required = 0
    for row in deduped.values():
        normalized = normalize_form4(row)
        if normalized is None:
            missing_required += 1
            continue
        usable.append(normalized)
    usable.sort(key=lambda row: (row["usable_trade_date"], row["ticker"], row["transaction_code"]))
    code_counts = Counter(row["transaction_code"] for row in usable)
    audit = {
        "source_artifact": repo_rel(FORM4_TRANSACTIONS),
        "raw_rows": len(raw_rows),
        "deduped_rows": len(deduped),
        "usable_rows": len(usable),
        "missing_required_rows": missing_required,
        "pit_safe_rows": sum(1 for row in usable if row["pit_safe_flag"]),
        "distinct_tickers": len({row["ticker"] for row in usable}),
        "usable_trade_date_min": min((row["usable_trade_date"] for row in usable), default=None),
        "usable_trade_date_max": max((row["usable_trade_date"] for row in usable), default=None),
        "transaction_code_counts": counter_dict(code_counts),
        "sale_rows": code_counts.get("S", 0),
        "sale_10b5_rows": sum(1 for row in usable if row["transaction_code"] == "S" and row["10b5_1_flag"]),
        "sale_non_10b5_rows": sum(1 for row in usable if row["transaction_code"] == "S" and not row["10b5_1_flag"]),
        "withholding_rows": code_counts.get("F", 0),
        "purchase_rows": code_counts.get("P", 0),
        "artifact_not_mutated": True,
    }
    return usable, audit


def summarize_events(events: list[dict[str, Any]], entry: date) -> dict[str, Any]:
    code_counts = Counter(row["transaction_code"] for row in events)
    relation_counts: Counter[str] = Counter()
    sale_retentions = [
        row["post_sale_retention_fraction"]
        for row in events
        if row["transaction_code"] == "S" and row["post_sale_retention_fraction"] is not None
    ]
    weighted_retention_num = 0.0
    weighted_retention_den = 0.0
    for row in events:
        retention = row["post_sale_retention_fraction"]
        value = row["transaction_value"]
        if row["transaction_code"] == "S" and retention is not None and value:
            weighted_retention_num += retention * value
            weighted_retention_den += value
    for row in events:
        usable = row["usable_trade_date_obj"]
        relation_counts["pre_entry_or_entry" if usable <= entry else "in_hold_after_entry"] += 1

    sale_value = sum(row["transaction_value"] for row in events if row["transaction_code"] == "S")
    sale_10b5_value = sum(
        row["transaction_value"]
        for row in events
        if row["transaction_code"] == "S" and row["10b5_1_flag"]
    )
    sale_non_10b5_value = sum(
        row["transaction_value"]
        for row in events
        if row["transaction_code"] == "S" and not row["10b5_1_flag"]
    )
    purchase_value = sum(row["transaction_value"] for row in events if row["transaction_code"] == "P")
    withholding_value = sum(row["transaction_value"] for row in events if row["transaction_code"] == "F")
    return {
        "event_count": len(events),
        "accession_count": len({row["accession_number"] for row in events if row.get("accession_number")}),
        "owner_count": len({row["owner_cik"] for row in events if row.get("owner_cik")}),
        "usable_trade_date_min": min((row["usable_trade_date"] for row in events), default=None),
        "usable_trade_date_max": max((row["usable_trade_date"] for row in events), default=None),
        "transaction_code_counts": counter_dict(code_counts),
        "relation_counts": counter_dict(relation_counts),
        "sale_rows": code_counts.get("S", 0),
        "sale_value": round(sale_value, 2),
        "sale_10b5_value": round(sale_10b5_value, 2),
        "sale_non_10b5_value": round(sale_non_10b5_value, 2),
        "purchase_rows": code_counts.get("P", 0),
        "purchase_value": round(purchase_value, 2),
        "withholding_rows": code_counts.get("F", 0),
        "withholding_value": round(withholding_value, 2),
        "option_exercise_rows": sum(1 for row in events if row["option_exercise_flag"]),
        "officer_rows": sum(1 for row in events if row["is_officer"]),
        "director_rows": sum(1 for row in events if row["is_director"]),
        "min_post_sale_retention_fraction": (
            round(min(sale_retentions), 6) if sale_retentions else None
        ),
        "weighted_post_sale_retention_fraction": (
            round(weighted_retention_num / weighted_retention_den, 6)
            if weighted_retention_den
            else None
        ),
        "has_sale_pressure": sale_value > 0,
        "has_non_10b5_sale_pressure": sale_non_10b5_value > 0,
        "has_purchase_support": purchase_value > 0,
        "compensation_plumbing_only": (
            len(events) > 0 and sale_value == 0 and purchase_value == 0 and code_counts.get("F", 0) > 0
        ),
    }


def attach_form4_context(
    forward_rows: list[dict[str, Any]],
    form4_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_ticker: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in form4_rows:
        by_ticker[row["ticker"]].append(row)

    output: list[dict[str, Any]] = []
    lookback = timedelta(days=int(CONFIG["lookback_days_before_entry"]))
    for row in forward_rows:
        entry = row["entry_date_obj"]
        exit_ = row["exit_date_obj"]
        start = entry - lookback
        events = [
            event
            for event in by_ticker.get(row["ticker"], [])
            if start <= event["usable_trade_date_obj"] <= exit_
        ]
        context = summarize_events(events, entry)
        output.append(
            {
                **{key: value for key, value in row.items() if not key.endswith("_obj")},
                "form4_context": context,
                "form4_bucket": classify_context(context),
            }
        )
    return output


def classify_context(context: dict[str, Any]) -> str:
    if not context["event_count"]:
        return "no_form4_context"
    if context["has_sale_pressure"]:
        return "sale_pressure"
    if context["has_purchase_support"]:
        return "purchase_support"
    if context["compensation_plumbing_only"]:
        return "compensation_plumbing_only"
    return "other_form4_context"


def field_stats(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    if not values:
        return {
            "n": 0,
            "sum": None,
            "mean": None,
            "median": None,
            "positive_rate": None,
            "min": None,
            "max": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(sum(values) / len(values), 2),
        "median": round(median(values), 2),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def summarize_forward_cohort(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = Counter(row["ticker"] for row in rows)
    ticker_count = len(tickers)
    max_ticker_share = (max(tickers.values()) / len(rows)) if rows else None
    return {
        "n": len(rows),
        "distinct_tickers": ticker_count,
        "ticker_counts": counter_dict(tickers),
        "max_ticker_share": round(max_ticker_share, 4) if max_ticker_share is not None else None,
        "sleeve_counts": counter_dict(Counter(row.get("sleeve_key") for row in rows)),
        **{field: field_stats(rows, field) for field in REPLACEMENT_FIELDS},
    }


def compare_cohorts(
    target: dict[str, Any],
    comparator: dict[str, Any],
    *,
    target_name: str,
    comparator_name: str,
) -> dict[str, Any]:
    by_field: dict[str, Any] = {}
    mean_underperform = 0
    median_underperform = 0
    for field in REPLACEMENT_FIELDS:
        target_mean = target[field]["mean"]
        comparator_mean = comparator[field]["mean"]
        target_median = target[field]["median"]
        comparator_median = comparator[field]["median"]
        mean_delta = (
            round(target_mean - comparator_mean, 2)
            if target_mean is not None and comparator_mean is not None
            else None
        )
        median_delta = (
            round(target_median - comparator_median, 2)
            if target_median is not None and comparator_median is not None
            else None
        )
        mean_is_weaker = bool(mean_delta is not None and mean_delta < 0)
        median_is_weaker = bool(median_delta is not None and median_delta < 0)
        mean_underperform += int(mean_is_weaker)
        median_underperform += int(median_is_weaker)
        by_field[field] = {
            "target_mean": target_mean,
            "comparator_mean": comparator_mean,
            "target_minus_comparator_mean": mean_delta,
            "target_median": target_median,
            "comparator_median": comparator_median,
            "target_minus_comparator_median": median_delta,
            "target_weaker_on_mean": mean_is_weaker,
            "target_weaker_on_median": median_is_weaker,
        }
    return {
        "target": target_name,
        "comparator": comparator_name,
        "by_field": by_field,
        "mean_underperform_fields": mean_underperform,
        "median_underperform_fields": median_underperform,
    }


def build_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cohorts = {
        "all_forward_rows": summarize_forward_cohort(rows),
        "no_form4_context": summarize_forward_cohort(
            [row for row in rows if row["form4_bucket"] == "no_form4_context"]
        ),
        "any_form4_context": summarize_forward_cohort(
            [row for row in rows if row["form4_bucket"] != "no_form4_context"]
        ),
        "sale_pressure": summarize_forward_cohort(
            [row for row in rows if row["form4_bucket"] == "sale_pressure"]
        ),
        "non_10b5_sale_pressure": summarize_forward_cohort(
            [
                row
                for row in rows
                if row["form4_context"]["has_non_10b5_sale_pressure"]
            ]
        ),
        "purchase_support": summarize_forward_cohort(
            [row for row in rows if row["form4_bucket"] == "purchase_support"]
        ),
        "compensation_plumbing_only": summarize_forward_cohort(
            [row for row in rows if row["form4_bucket"] == "compensation_plumbing_only"]
        ),
        "pre_entry_or_entry_context": summarize_forward_cohort(
            [
                row
                for row in rows
                if row["form4_context"]["relation_counts"].get("pre_entry_or_entry", 0) > 0
            ]
        ),
        "in_hold_after_entry_context": summarize_forward_cohort(
            [
                row
                for row in rows
                if row["form4_context"]["relation_counts"].get("in_hold_after_entry", 0) > 0
            ]
        ),
    }
    return {
        "all_rows": {
            "n": len(rows),
            "bucket_counts": counter_dict(Counter(row["form4_bucket"] for row in rows)),
            "matched_rows": cohorts["any_form4_context"]["n"],
            "matched_tickers": cohorts["any_form4_context"]["distinct_tickers"],
            "sale_pressure_rows": cohorts["sale_pressure"]["n"],
            "sale_pressure_tickers": cohorts["sale_pressure"]["distinct_tickers"],
        },
        "cohorts": cohorts,
        "sale_pressure_vs_no_form4_context": compare_cohorts(
            cohorts["sale_pressure"],
            cohorts["no_form4_context"],
            target_name="sale_pressure",
            comparator_name="no_form4_context",
        ),
        "any_form4_vs_no_form4_context": compare_cohorts(
            cohorts["any_form4_context"],
            cohorts["no_form4_context"],
            target_name="any_form4_context",
            comparator_name="no_form4_context",
        ),
    }


def evaluate_gate4(analysis: dict[str, Any]) -> dict[str, Any]:
    sale = analysis["cohorts"]["sale_pressure"]
    any_context = analysis["cohorts"]["any_form4_context"]
    comparison = analysis["sale_pressure_vs_no_form4_context"]
    failed: list[str] = []

    if any_context["n"] < CONFIG["min_any_form4_rows"]:
        failed.append("form4_forward_overlap_too_thin")
    if sale["n"] < CONFIG["min_sale_pressure_rows"]:
        failed.append("sale_pressure_rows_below_min")
    if sale["distinct_tickers"] < CONFIG["min_sale_pressure_tickers"]:
        failed.append("sale_pressure_tickers_below_min")
    if (
        sale["max_ticker_share"] is not None
        and sale["max_ticker_share"] > CONFIG["max_single_ticker_sale_pressure_share"]
    ):
        failed.append("sale_pressure_ticker_concentration_too_high")
    if comparison["mean_underperform_fields"] < CONFIG["min_underperform_mean_fields"]:
        failed.append("sale_pressure_not_weaker_on_enough_mean_fields")
    if comparison["median_underperform_fields"] < CONFIG["min_underperform_median_fields"]:
        failed.append("sale_pressure_not_weaker_on_enough_median_fields")

    observed_only_lead = not failed
    return {
        "passed": False,
        "observed_only_lead": observed_only_lead,
        "allocation_ready": False,
        "decision": (
            "observed_only_positive_form4_sale_pressure_lead_not_promoted"
            if observed_only_lead
            else "rejected_form4_forward_context_not_allocation_ready"
        ),
        "failed_reasons": failed,
        "acceptance_rule": (
            "Observed-only positive lead only if sale-pressure rows have enough "
            "sample, two tickers, acceptable concentration, and weaker replacement "
            "value than no-Form4 rows on at least two mean and median comparators."
        ),
        "source_saturation_context": {
            "form4_candidate_pool_source_saturated": True,
            "override_basis": NEW_EVIDENCE_AXIS,
            "promotion_allowed": False,
        },
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
    }


def calibration(prediction: dict[str, Any], success: bool, failed_reasons: list[str]) -> dict[str, Any]:
    declared = set(prediction.get("main_failure_modes") or [])
    observed: list[str] = []
    reason_text = " ".join(failed_reasons)
    if "thin" in reason_text or "below_min" in reason_text:
        observed.append("form4_forward_overlap_too_thin")
    if "not_weaker" in reason_text:
        observed.append("no_replacement_separation")
    if "concentration" in reason_text:
        observed.append("single_ticker_concentration")
    if not observed and not success:
        observed.append("unexpected_failure_mode")
    return {
        "predicted_success_probability": prediction.get("success_probability"),
        "outcome_success": bool(success),
        "failure_modes_observed": observed,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "predicted_failure_mode_hit": bool(declared & set(observed)),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
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
        "attribution": {
            "source_audit": payload["attribution"]["source_audit"],
            "all_rows": analysis["all_rows"],
            "cohorts": analysis["cohorts"],
            "sale_pressure_vs_no_form4_context": analysis["sale_pressure_vs_no_form4_context"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "updated_at": payload["timestamp"],
        "anti_js": payload["anti_js"],
    }


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    sale = analysis["cohorts"]["sale_pressure"]
    no_context = analysis["cohorts"]["no_form4_context"]
    comparison = analysis["sale_pressure_vs_no_form4_context"]["by_field"]
    rows = [
        "| Comparator | Sale Mean | No Form4 Mean | Delta Mean | Sale Median | Delta Median |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field in REPLACEMENT_FIELDS:
        rows.append(
            "| {field} | {sale_mean} | {comp_mean} | {delta_mean} | {sale_median} | {delta_median} |".format(
                field=field,
                sale_mean=money(sale[field]["mean"]),
                comp_mean=money(no_context[field]["mean"]),
                delta_mean=money(comparison[field]["target_minus_comparator_mean"]),
                sale_median=money(sale[field]["median"]),
                delta_median=money(comparison[field]["target_minus_comparator_median"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: Form4 forward conflict readiness",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            "- Shared helper promoted: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Cohort Summary",
            "",
            f"- Forward rows: `{analysis['all_rows']['n']}`",
            f"- Any Form4 context rows: `{analysis['all_rows']['matched_rows']}`",
            f"- Sale-pressure rows: `{sale['n']}` across `{sale['distinct_tickers']}` tickers",
            f"- Sale-pressure max ticker share: `{sale['max_ticker_share']}`",
            "",
            "## Sale Pressure vs No Form4 Context",
            "",
            *rows,
            "",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        FORWARD_REPLACEMENT,
        FORM4_TRANSACTIONS,
        BASELINE_RESULT,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in paths},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    forward_rows, forward_audit = load_forward_rows()
    form4_rows, form4_audit = load_form4_rows()
    enriched_rows = attach_form4_context(forward_rows, form4_rows)
    analysis = build_analysis(enriched_rows)
    gate4 = evaluate_gate4(analysis)
    status = (
        "observed_only_positive_lead"
        if gate4["observed_only_lead"]
        else "observed_only_rejected"
    )
    decision = str(gate4["decision"])
    why_result = (
        "Current daily Form4 sale pressure did separate closed forward replacement "
        "rows, but the experiment remains observed-only and source-saturation "
        "prevents direct promotion."
        if gate4["observed_only_lead"]
        else "Current daily Form4 context did not clear the fixed observed-only "
        "screen; the source remains saturated and the closed forward ledger is "
        "too small or not directionally weaker enough to justify a retry."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": gate4["observed_only_lead"],
        "lane": "alpha_search",
        "owner": OWNER,
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
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation hit Form4 near-neighbor families and source "
                    "saturation; override was recorded only for the non-scan "
                    "forward replacement join evidence axis."
                ),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One read-only attribution bundle: join current daily Form4 XML "
                "transactions to existing closed forward replacement rows by "
                "same ticker and PIT date window."
            ),
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "forward_source_artifact": repo_rel(FORWARD_REPLACEMENT),
            "form4_source_artifact": repo_rel(FORM4_TRANSACTIONS),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
            "replacement_fields": REPLACEMENT_FIELDS,
            "pit_window_rule": (
                "same ticker and usable_trade_date between entry_date minus "
                "lookback_days_before_entry and exit_date inclusive"
            ),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_summary": baseline,
            "note": "Observed-only attribution; before and after strategy policy are identical.",
        },
        "gate2": {
            "passed": bool(forward_rows) and bool(form4_rows),
            "source_audit": {
                "forward_replacement": forward_audit,
                "form4_transactions": form4_audit,
            },
            "required_fields": [
                "entry_date",
                "exit_date",
                "ticker",
                "usable_trade_date",
                "transaction_code",
                *REPLACEMENT_FIELDS,
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in forward_rows),
            "target_price": {
                "available": False,
                "source": "not_applicable_observed_only_forward_replacement_rows",
                "reason": "No executable target, entry, exit, order, or paper ledger mutation is scheduled.",
            },
        },
        "gate3": {
            "strategy_filter_added": False,
            "signals_generated": forward_audit["usable_rows"],
            "signals_survived": forward_audit["usable_rows"],
            "survival_rate": 1.0 if forward_audit["usable_rows"] else None,
            "context_match_rows": analysis["all_rows"]["matched_rows"],
            "context_match_rate": (
                round(analysis["all_rows"]["matched_rows"] / forward_audit["usable_rows"], 4)
                if forward_audit["usable_rows"]
                else None
            ),
            "baseline_survival_rate": baseline["survival_rate"],
            "passed": True,
            "note": "No executable filter was added; context match rate is diagnostic only.",
        },
        "gate4": gate4,
        "before_metrics": baseline,
        "after_metrics": baseline | {"strategy_behavior_changed": False},
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "source_audit": {
                "forward_replacement": forward_audit,
                "form4_transactions": form4_audit,
            },
            "analysis": analysis,
            "sample_rows": enriched_rows[:10],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "trade_enabled": False,
            "daily_snapshot_exposed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "parity_note": "Read-only attribution over existing Form4 and forward replacement artifacts.",
        },
        "calibration": calibration(prediction, gate4["observed_only_lead"], gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": why_result,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing Form4 transaction-code lists, role filters, "
                "10b5-1 handling, retention thresholds, date windows, hold days, "
                "top-N selection, or notional sizing on the same current forward rows."
            ),
            "new_evidence_required": (
                "Need materially more closed forward replacement rows from the "
                "shared daily Form4 helper, explicit Form 144 plan/float context, "
                "or executive ownership and compensation provenance before another "
                "Form4 conflict alpha attempt."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(FORM4_TRANSACTIONS),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260616-012.json",
            "experiments/logs/exp-20260616-013.json",
            "experiments/logs/exp-20260623-024.json",
            "experiments/logs/exp-20260624-008.json",
            "docs/backtesting.md",
            "docs/production_backtest_parity.md",
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
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
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
        "observed_only_lead": payload["gate4"]["observed_only_lead"],
        "allocation_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "attribution": {
            "source_audit": payload["attribution"]["source_audit"],
            "all_rows": payload["attribution"]["analysis"]["all_rows"],
            "cohorts": payload["attribution"]["analysis"]["cohorts"],
            "sale_pressure_vs_no_form4_context": payload["attribution"]["analysis"][
                "sale_pressure_vs_no_form4_context"
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
    analysis = payload["attribution"]["analysis"]
    sale = analysis["cohorts"]["sale_pressure"]
    comparison = analysis["sale_pressure_vs_no_form4_context"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "forward_rows": analysis["all_rows"]["n"],
                "any_form4_context_rows": analysis["all_rows"]["matched_rows"],
                "sale_pressure_rows": sale["n"],
                "sale_pressure_tickers": sale["distinct_tickers"],
                "mean_underperform_fields": comparison["mean_underperform_fields"],
                "median_underperform_fields": comparison["median_underperform_fields"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "sale_pressure_cash_mean": sale["replacement_value_vs_cash_usd"]["mean"],
                "sale_pressure_spy_mean": sale["replacement_value_vs_spy_usd"]["mean"],
                "sale_pressure_qqq_mean": sale["replacement_value_vs_qqq_usd"]["mean"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
