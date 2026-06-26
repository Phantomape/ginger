"""exp-20260625-016: SEC FTD forward replacement context.

Observed-only alpha attribution. This runner joins existing closed forward
replacement-value rows to PIT SEC FTD publication rows. It does not alter any
strategy helper, candidate ranking, sizing, entry, exit, paper order, live
order, or daily sleeve artifact.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260625-016"
OWNER = "alpha-explore"
SLUG = "sec_ftd_forward_replacement_context"
RUNNER = f"quant/experiments/exp_20260625_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_016_{SLUG}.json"
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
SEC_FTD_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "sec_ftd" / "rows.json"

HYPOTHESIS = (
    "Observed-only alpha hypothesis: latest closed forward replacement rows "
    "joined to PIT SEC FTD publication pressure may show whether "
    "accepted/default-off rows with current FTD pressure have stronger "
    "replacement value; this is not a FINRA/FTD threshold replay and makes no "
    "strategy behavior change."
)
CHANGE_TYPE = "observed_only_forward_attribution"
MECHANISM_FAMILY = "observed_only_forward_attribution"
TRIAL_FAMILY = "sec_ftd_forward_replacement_context_attribution"
TRIAL_VARIANT_ID = "pit_publication_current_forward_rows_v1"
CHANGED_VARIABLE = "sec_ftd_forward_replacement_context_attribution_v1"
NEW_EVIDENCE_TYPE = "closed_forward_replacement_rows_joined_to_pit_sec_ftd_publications"
NEW_EVIDENCE_AXIS = (
    "Read-only forward evidence axis: latest closed forward_replacement_value "
    "rows joined to already-cached PIT SEC FTD publication rows by same ticker "
    "and entry-date-known publication window. This is not a FINRA, FTD "
    "threshold, top-N, hold-day, notional, or replay-window retry."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260604-027",
    "exp-20260614-003",
    "exp-20260615-015",
    "exp-20260619-010",
]
CAUSAL_COMPONENTS = [
    "closed forward replacement rows",
    "PIT SEC FTD publication join",
    "no strategy behavior change",
]
REPLACEMENT_FIELDS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONFIG = {
    "max_publication_age_days": 45,
    "min_ftd_notional_usd": 1_000_000.0,
    "min_ftd_shares": 100_000.0,
    "min_pressure_rows": 6,
    "min_pressure_tickers": 3,
    "max_single_ticker_pressure_share": 0.60,
    "min_better_mean_fields": 2,
    "min_better_median_fields": 2,
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


def counter_dict(counter: Counter[Any], limit: int | None = None) -> dict[str, int]:
    rows = counter.most_common(limit)
    return {str(key): int(value) for key, value in rows}


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


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {}) or {}
    prediction = ticket.get("prediction")
    if isinstance(prediction, dict) and prediction:
        return prediction
    return {
        "success_probability": 0.14,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "forward_ftd_overlap_too_thin",
            "accepted_ftd_family_frozen",
            "no_replacement_separation",
            "missing_finra_borrow_context",
        ],
        "confidence_reason": (
            "SEC FTD+FINRA is accepted as default-off but frozen for threshold "
            "retunes; current closed forward replacement rows are the only new "
            "evidence tested here."
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
        "distinct_sleeves": len({row["sleeve_key"] for row in usable}),
        "artifact_not_mutated": True,
    }
    return usable, audit


def normalize_ftd(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper()
    settlement = as_date(row.get("settlement_date"))
    publication = as_date(row.get("publication_date"))
    usable_trade = as_date(row.get("usable_trade_date"))
    ftd_shares = as_float(row.get("ftd_shares"))
    ftd_notional = as_float(row.get("ftd_notional"))
    ftd_price = as_float(row.get("ftd_price"))
    if not ticker or publication is None or ftd_shares is None or ftd_notional is None:
        return None
    return {
        "ticker": ticker,
        "settlement_date": settlement.isoformat() if settlement else None,
        "publication_date": publication.isoformat(),
        "usable_trade_date": usable_trade.isoformat() if usable_trade else None,
        "publication_date_obj": publication,
        "settlement_date_obj": settlement,
        "usable_trade_date_obj": usable_trade,
        "ftd_shares": ftd_shares,
        "ftd_price": ftd_price,
        "ftd_notional": ftd_notional,
        "pit_safe": bool(row.get("pit_safe")),
        "source_url": row.get("source_url"),
        "source_page": row.get("source_page"),
    }


def load_ftd_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = read_json(SEC_FTD_ROWS, {}) or {}
    raw_rows = payload.get("rows") if isinstance(payload, dict) else []
    if not isinstance(raw_rows, list):
        raw_rows = []
    usable: list[dict[str, Any]] = []
    missing_required = 0
    for row in raw_rows:
        if not isinstance(row, dict):
            missing_required += 1
            continue
        normalized = normalize_ftd(row)
        if normalized is None:
            missing_required += 1
            continue
        usable.append(normalized)
    usable.sort(
        key=lambda row: (
            row["ticker"],
            row["publication_date"],
            row.get("settlement_date") or "",
        )
    )
    audit = {
        "source_artifact": repo_rel(SEC_FTD_ROWS),
        "raw_rows": len(raw_rows),
        "usable_rows": len(usable),
        "missing_required_rows": missing_required,
        "publication_date_min": min((row["publication_date"] for row in usable), default=None),
        "publication_date_max": max((row["publication_date"] for row in usable), default=None),
        "settlement_date_min": min(
            (row["settlement_date"] for row in usable if row["settlement_date"]),
            default=None,
        ),
        "settlement_date_max": max(
            (row["settlement_date"] for row in usable if row["settlement_date"]),
            default=None,
        ),
        "usable_trade_date_min": min(
            (row["usable_trade_date"] for row in usable if row["usable_trade_date"]),
            default=None,
        ),
        "usable_trade_date_max": max(
            (row["usable_trade_date"] for row in usable if row["usable_trade_date"]),
            default=None,
        ),
        "distinct_tickers": len({row["ticker"] for row in usable}),
        "pit_safe_rows": sum(1 for row in usable if row["pit_safe"]),
        "artifact_not_mutated": True,
    }
    return usable, audit


def serializable_ftd_row(row: dict[str, Any] | None, entry: date | None = None) -> dict[str, Any] | None:
    if row is None:
        return None
    publication = row.get("publication_date_obj")
    age = (entry - publication).days if isinstance(publication, date) and entry else None
    return {
        "settlement_date": row.get("settlement_date"),
        "publication_date": row.get("publication_date"),
        "usable_trade_date": row.get("usable_trade_date"),
        "publication_age_days": age,
        "ftd_shares": row.get("ftd_shares"),
        "ftd_price": row.get("ftd_price"),
        "ftd_notional": row.get("ftd_notional"),
        "pit_safe": row.get("pit_safe"),
        "source_page": row.get("source_page"),
    }


def attach_ftd_context(
    forward_rows: list[dict[str, Any]],
    ftd_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ftd_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ftd_rows:
        ftd_by_ticker[row["ticker"]].append(row)

    enriched: list[dict[str, Any]] = []
    max_age = int(CONFIG["max_publication_age_days"])
    min_notional = float(CONFIG["min_ftd_notional_usd"])
    min_shares = float(CONFIG["min_ftd_shares"])

    for row in forward_rows:
        entry = as_date(row.get("entry_date"))
        eligible: list[dict[str, Any]] = []
        if entry is not None:
            for ftd_row in ftd_by_ticker.get(str(row.get("ticker") or "").upper(), []):
                publication = ftd_row["publication_date_obj"]
                if publication > entry:
                    continue
                age_days = (entry - publication).days
                if age_days < 0 or age_days > max_age:
                    continue
                eligible.append(ftd_row)

        latest = max(
            eligible,
            key=lambda item: (item["publication_date_obj"], item.get("settlement_date_obj") or date.min),
            default=None,
        )
        pressure_rows = [
            item
            for item in eligible
            if float(item.get("ftd_notional") or 0.0) >= min_notional
            and float(item.get("ftd_shares") or 0.0) >= min_shares
        ]
        pressure = max(
            pressure_rows,
            key=lambda item: (item["publication_date_obj"], item.get("settlement_date_obj") or date.min),
            default=None,
        )
        window_notional_values = [float(item.get("ftd_notional") or 0.0) for item in eligible]
        window_share_values = [float(item.get("ftd_shares") or 0.0) for item in eligible]
        enriched.append(
            {
                **row,
                "has_sec_ftd_context": bool(eligible),
                "sec_ftd_window_rows": len(eligible),
                "sec_ftd_pressure_component": pressure is not None,
                "sec_ftd_window_notional_sum": round(sum(window_notional_values), 2),
                "sec_ftd_window_notional_max": round(max(window_notional_values), 2)
                if window_notional_values
                else None,
                "sec_ftd_window_shares_max": round(max(window_share_values), 2)
                if window_share_values
                else None,
                "sec_ftd_latest": serializable_ftd_row(latest, entry),
                "sec_ftd_pressure": serializable_ftd_row(pressure, entry),
            }
        )
    return enriched


def field_stats(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows if as_float(row.get(field)) is not None]
    if not values:
        return {
            "n": 0,
            "sum": 0.0,
            "mean": None,
            "median": None,
            "positive_rate": None,
            "min": None,
            "max": None,
        }
    return {
        "n": len(values),
        "sum": round(sum(values), 2),
        "mean": round(sum(values) / len(values), 4),
        "median": round(float(median(values)), 4),
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def cohort_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ticker_counts = Counter(row.get("ticker") for row in rows)
    sleeve_counts = Counter(row.get("sleeve_key") for row in rows)
    max_count = max(ticker_counts.values(), default=0)
    stats: dict[str, Any] = {
        "n": len(rows),
        "distinct_tickers": len(ticker_counts),
        "distinct_sleeves": len(sleeve_counts),
        "ticker_counts": counter_dict(ticker_counts, 12),
        "sleeve_counts": counter_dict(sleeve_counts, 12),
        "max_ticker_share": round(max_count / len(rows), 4) if rows else None,
        "entry_date_min": min((str(row.get("entry_date")) for row in rows), default=None),
        "entry_date_max": max((str(row.get("entry_date")) for row in rows), default=None),
        "exit_date_min": min((str(row.get("exit_date")) for row in rows), default=None),
        "exit_date_max": max((str(row.get("exit_date")) for row in rows), default=None),
        "sec_ftd_window_rows_sum": sum(int(row.get("sec_ftd_window_rows") or 0) for row in rows),
    }
    for field in REPLACEMENT_FIELDS:
        stats[field] = field_stats(rows, field)
    return stats


def compare_cohorts(
    target: dict[str, Any],
    comparator: dict[str, Any],
) -> dict[str, Any]:
    by_field: dict[str, dict[str, Any]] = {}
    mean_better = 0
    median_better = 0
    for field in REPLACEMENT_FIELDS:
        target_field = target[field]
        comparator_field = comparator[field]
        target_mean = target_field["mean"]
        comparator_mean = comparator_field["mean"]
        target_median = target_field["median"]
        comparator_median = comparator_field["median"]
        mean_delta = (
            round(float(target_mean) - float(comparator_mean), 4)
            if target_mean is not None and comparator_mean is not None
            else None
        )
        median_delta = (
            round(float(target_median) - float(comparator_median), 4)
            if target_median is not None and comparator_median is not None
            else None
        )
        if mean_delta is not None and mean_delta > 0:
            mean_better += 1
        if median_delta is not None and median_delta > 0:
            median_better += 1
        by_field[field] = {
            "target_mean": target_mean,
            "comparator_mean": comparator_mean,
            "target_minus_comparator_mean": mean_delta,
            "target_median": target_median,
            "comparator_median": comparator_median,
            "target_minus_comparator_median": median_delta,
        }
    return {
        "by_field": by_field,
        "mean_better_fields": mean_better,
        "median_better_fields": median_better,
    }


def build_analysis(enriched_rows: list[dict[str, Any]]) -> dict[str, Any]:
    any_ftd = [row for row in enriched_rows if row["has_sec_ftd_context"]]
    no_ftd = [row for row in enriched_rows if not row["has_sec_ftd_context"]]
    pressure = [row for row in enriched_rows if row["sec_ftd_pressure_component"]]
    no_pressure = [row for row in enriched_rows if not row["sec_ftd_pressure_component"]]
    low_context = [
        row
        for row in enriched_rows
        if row["has_sec_ftd_context"] and not row["sec_ftd_pressure_component"]
    ]
    cohorts = {
        "all_rows": cohort_stats(enriched_rows),
        "any_sec_ftd_context": cohort_stats(any_ftd),
        "no_sec_ftd_context": cohort_stats(no_ftd),
        "accepted_ftd_pressure_component": cohort_stats(pressure),
        "no_pressure_component": cohort_stats(no_pressure),
        "low_ftd_context": cohort_stats(low_context),
    }
    all_rows = cohorts["all_rows"] | {
        "matched_rows": len(any_ftd),
        "pressure_component_rows": len(pressure),
        "context_match_rate": round(len(any_ftd) / len(enriched_rows), 4) if enriched_rows else None,
        "pressure_component_rate": round(len(pressure) / len(enriched_rows), 4)
        if enriched_rows
        else None,
    }
    cohorts["all_rows"] = all_rows
    return {
        "all_rows": all_rows,
        "cohorts": cohorts,
        "pressure_vs_no_pressure_component": compare_cohorts(
            cohorts["accepted_ftd_pressure_component"],
            cohorts["no_pressure_component"],
        ),
        "pressure_vs_no_sec_ftd_context": compare_cohorts(
            cohorts["accepted_ftd_pressure_component"],
            cohorts["no_sec_ftd_context"],
        ),
    }


def evaluate_gate4(analysis: dict[str, Any]) -> dict[str, Any]:
    pressure = analysis["cohorts"]["accepted_ftd_pressure_component"]
    comparison = analysis["pressure_vs_no_pressure_component"]
    failed_reasons: list[str] = []
    blockers: list[str] = [
        "missing_finra_short_volume_confirmation_in_forward_join",
        "missing_borrow_fee_or_loan_availability_context",
        "accepted_sec_ftd_finra_family_remains_default_off",
    ]

    if pressure["n"] < int(CONFIG["min_pressure_rows"]):
        failed_reasons.append("pressure_component_sample_below_min")
    if pressure["distinct_tickers"] < int(CONFIG["min_pressure_tickers"]):
        failed_reasons.append("pressure_component_ticker_breadth_below_min")
    max_share = pressure["max_ticker_share"]
    if max_share is not None and max_share > float(CONFIG["max_single_ticker_pressure_share"]):
        failed_reasons.append("pressure_component_concentration_too_high")
    if comparison["mean_better_fields"] < int(CONFIG["min_better_mean_fields"]):
        failed_reasons.append("mean_replacement_separation_below_min")
    if comparison["median_better_fields"] < int(CONFIG["min_better_median_fields"]):
        failed_reasons.append("median_replacement_separation_below_min")

    observed_only_lead = not failed_reasons
    decision = (
        "observed_only_positive_sec_ftd_forward_context_lead_not_promoted"
        if observed_only_lead
        else "rejected_no_sec_ftd_forward_replacement_context_edge"
    )
    return {
        "passed": observed_only_lead,
        "observed_only_lead": observed_only_lead,
        "decision": decision,
        "failed_reasons": failed_reasons,
        "promotion_blockers": blockers,
        "acceptance_rule": (
            "Observed-only lead requires at least "
            f"{CONFIG['min_pressure_rows']} fixed SEC FTD pressure-component "
            f"rows, at least {CONFIG['min_pressure_tickers']} tickers, max "
            f"ticker share <= {CONFIG['max_single_ticker_pressure_share']}, "
            f"and pressure rows beating non-pressure rows on at least "
            f"{CONFIG['min_better_mean_fields']} mean and "
            f"{CONFIG['min_better_median_fields']} median replacement fields. "
            "Even a lead cannot promote or retune SEC FTD+FINRA without FINRA "
            "confirmation, borrow context, and separate Gate 1-4 activation."
        ),
        "comparison": comparison,
    }


def calibration(
    prediction: dict[str, Any],
    observed_only_lead: bool,
    failed_reasons: list[str],
) -> dict[str, Any]:
    probability = as_float(prediction.get("success_probability"))
    return {
        "predicted_success_probability": probability,
        "actual_observed_only_lead": observed_only_lead,
        "calibration_note": (
            "Low-confidence prediction was correct: no observed-only lead emerged."
            if not observed_only_lead
            else "Low-confidence prediction missed a positive observed-only lead."
        ),
        "primary_failure_modes_realized": failed_reasons,
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
        "multiple_testing_risk_bucket": "minimal",
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
            "pressure_vs_no_pressure_component": analysis[
                "pressure_vs_no_pressure_component"
            ],
            "pressure_vs_no_sec_ftd_context": analysis["pressure_vs_no_sec_ftd_context"],
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
    pressure = analysis["cohorts"]["accepted_ftd_pressure_component"]
    no_pressure = analysis["cohorts"]["no_pressure_component"]
    comparison = analysis["pressure_vs_no_pressure_component"]["by_field"]
    rows = [
        "| Comparator | Pressure Mean | Non-Pressure Mean | Delta Mean | Pressure Median | Delta Median |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field in REPLACEMENT_FIELDS:
        rows.append(
            "| {field} | {pressure_mean} | {comp_mean} | {delta_mean} | "
            "{pressure_median} | {delta_median} |".format(
                field=field,
                pressure_mean=money(pressure[field]["mean"]),
                comp_mean=money(no_pressure[field]["mean"]),
                delta_mean=money(comparison[field]["target_minus_comparator_mean"]),
                pressure_median=money(pressure[field]["median"]),
                delta_median=money(comparison[field]["target_minus_comparator_median"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC FTD forward replacement context",
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
            f"- Any SEC FTD context rows: `{analysis['all_rows']['matched_rows']}`",
            "- SEC FTD pressure-component rows: "
            f"`{pressure['n']}` across `{pressure['distinct_tickers']}` tickers",
            f"- Pressure-component max ticker share: `{pressure['max_ticker_share']}`",
            "",
            "## Pressure Component vs Non-Pressure",
            "",
            *rows,
            "",
            f"- Failed reasons: `{', '.join(payload['gate4']['failed_reasons']) or 'none'}`",
            "- Promotion blockers: "
            f"`{', '.join(payload['gate4']['promotion_blockers'])}`",
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
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        FORWARD_REPLACEMENT,
        SEC_FTD_ROWS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "decision": payload["decision"],
        "status": payload["status"],
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in paths
        },
        "reproduction_commands": payload["reproduction_commands"],
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    forward_rows, forward_audit = load_forward_rows()
    ftd_rows, ftd_audit = load_ftd_rows()
    enriched_rows = attach_ftd_context(forward_rows, ftd_rows)
    analysis = build_analysis(enriched_rows)
    gate4 = evaluate_gate4(analysis)
    status = (
        "observed_only_positive_lead"
        if gate4["observed_only_lead"]
        else "observed_only_rejected"
    )
    decision = str(gate4["decision"])
    why_result = (
        "Latest forward replacement rows produced a fixed SEC FTD pressure "
        "component lead, but promotion remains blocked by missing FINRA and "
        "borrow context plus the accepted default-off boundary."
        if gate4["observed_only_lead"]
        else "Latest forward replacement rows did not clear the fixed "
        "observed-only SEC FTD pressure-component screen; sample, breadth, "
        "concentration, or replacement-value separation remains insufficient."
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
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation passed without override. Nearest neighbors "
                    "were accepted/frozen SEC FTD+FINRA families, but this run "
                    "uses only latest closed forward replacement rows as a "
                    "non-retune evidence axis."
                ),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "new_evidence_axis": NEW_EVIDENCE_AXIS,
            },
            "3_single_policy_bundle": (
                "One read-only attribution bundle: join existing closed "
                "forward replacement rows to PIT SEC FTD publication rows by "
                "same ticker and pre-entry publication window."
            ),
            "4_success_failure_standard": gate4["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "forward_source_artifact": repo_rel(FORWARD_REPLACEMENT),
            "sec_ftd_source_artifact": repo_rel(SEC_FTD_ROWS),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
            "replacement_fields": REPLACEMENT_FIELDS,
            "pit_window_rule": (
                "same ticker and SEC FTD publication_date <= entry_date with "
                "entry_date - publication_date <= max_publication_age_days"
            ),
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_summary": baseline,
            "note": "Observed-only attribution; before and after strategy policy are identical.",
        },
        "gate2": {
            "passed": bool(forward_rows) and bool(ftd_rows),
            "source_audit": {
                "forward_replacement": forward_audit,
                "sec_ftd": ftd_audit,
            },
            "required_fields": [
                "entry_date",
                "exit_date",
                "ticker",
                "publication_date",
                "ftd_shares",
                "ftd_notional",
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
            "context_match_rate": analysis["all_rows"]["context_match_rate"],
            "pressure_component_rows": analysis["all_rows"]["pressure_component_rows"],
            "pressure_component_rate": analysis["all_rows"]["pressure_component_rate"],
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
                "sec_ftd": ftd_audit,
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
            "parity_note": "Read-only attribution over existing SEC FTD and forward replacement artifacts.",
        },
        "calibration": calibration(prediction, gate4["observed_only_lead"], gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": why_result,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing SEC FTD notional, share, age, "
                "freshness, top-N, hold-day, notional, or FINRA-confirmation "
                "thresholds on the same current forward rows."
            ),
            "new_evidence_required": (
                "Need materially more closed SEC_FTD_FINRA true-trigger forward "
                "rows, PIT borrow fee or loan-availability context, or a "
                "separate mature activation ledger before revisiting this lane."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(SEC_FTD_ROWS),
            repo_rel(BASELINE_RESULT),
            "quant/sec_ftd_finra_paper_sleeve.py",
            "experiments/logs/exp-20260604-027.json",
            "experiments/logs/exp-20260614-003.json",
            "experiments/logs/exp-20260615-015.json",
            "experiments/logs/exp-20260619-010.json",
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
            "pressure_vs_no_pressure_component": payload["attribution"]["analysis"][
                "pressure_vs_no_pressure_component"
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
            "multiple_testing_risk_bucket": "minimal",
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
    pressure = analysis["cohorts"]["accepted_ftd_pressure_component"]
    comparison = analysis["pressure_vs_no_pressure_component"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "forward_rows": analysis["all_rows"]["n"],
                "any_sec_ftd_context_rows": analysis["all_rows"]["matched_rows"],
                "pressure_component_rows": pressure["n"],
                "pressure_component_tickers": pressure["distinct_tickers"],
                "mean_better_fields": comparison["mean_better_fields"],
                "median_better_fields": comparison["median_better_fields"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "promotion_blockers": payload["gate4"]["promotion_blockers"],
                "pressure_cash_mean": pressure["replacement_value_vs_cash_usd"]["mean"],
                "pressure_spy_mean": pressure["replacement_value_vs_spy_usd"]["mean"],
                "pressure_qqq_mean": pressure["replacement_value_vs_qqq_usd"]["mean"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
