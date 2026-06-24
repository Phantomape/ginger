"""exp-20260623-028: stock vs ETF forward replacement attribution.

Observed-only alpha attribution. This runner tests whether the currently closed
forward replacement-value evidence is diversified stock alpha or mostly
QQQ/ETF beta. It changes no strategy helper, daily snapshot, ranking, sizing,
exit, ledger, or order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260623-028"
OWNER = "alpha-explore"
SLUG = "forward_stock_vs_etf_replacement"
RUNNER = f"quant/experiments/exp_20260623_028_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_028_{SLUG}.json"
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

HYPOTHESIS = (
    "If the closed forward replacement rows are a real candidate-pool lead "
    "rather than QQQ/ETF beta, then stock-only rows should show positive "
    "replacement value versus cash, SPY, and QQQ with diversified ticker and "
    "sleeve support; otherwise activation remains blocked."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "default_off_paper_candidate_pool_forward_value"
TRIAL_FAMILY = "forward_replacement_stock_vs_etf_diversification"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = (
    "Stock-only versus ETF-only composition attribution on enriched forward "
    "replacement value rows; no ranking, sizing, entry, exit, or live policy "
    "change."
)
NEW_EVIDENCE_TYPE = "forward_replacement_composition_attribution"
NEW_EVIDENCE_AXIS = (
    "New gate shape: split enriched closed forward replacement rows by "
    "stock-only versus ETF-only composition to test whether the current "
    "forward lead is diversified stock alpha or QQQ/ETF beta. This is not an "
    "activation threshold relaxation, regime-scalar retune, or sleeve "
    "parameter sweep."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-013",
    "exp-20260623-019",
    "exp-20260623-027",
]
CAUSAL_COMPONENTS = [
    "read-only forward replacement rows",
    "fixed ETF ticker set versus stock ticker split",
    "cash/SPY/QQQ replacement-value attribution",
    "ticker and sleeve concentration checks",
    "no strategy behavior change",
]
ETF_TICKERS = {
    "DIA",
    "IWM",
    "QQQ",
    "SPY",
    "VTI",
    "VOO",
    "IVV",
    "XLK",
    "SMH",
    "SOXX",
}
REPLACEMENT_FIELDS = [
    "replacement_value_vs_cash_usd",
    "replacement_value_vs_spy_usd",
    "replacement_value_vs_qqq_usd",
]
CONFIG = {
    "min_stock_rows": 15,
    "min_distinct_stock_tickers": 8,
    "max_single_ticker_positive_cash_share": 0.50,
    "min_stock_mean_comparator_wins": 2,
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
        for raw in handle:
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
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


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
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


def as_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        output = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(output):
        return None
    return output


def round_or_none(value: Any, digits: int = 6) -> float | None:
    number = as_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if prediction:
        return prediction
    return {
        "recorded_at": utc_now(),
        "success_probability": 0.34,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "stock rows too few",
            "stock replacement value dominated by one ticker",
            "ETF rows explain most value",
            "benchmark-adjusted replacement value negative",
        ],
        "confidence_reason": (
            "Forward rows are enriched but sparse; prior readiness failed, "
            "while sleeve summaries hinted non-ETF rows may still have "
            "positive replacement value."
        ),
    }


def load_baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = list(payload.get("windows") or [])
    generated = sum(int(window.get("signals_generated") or 0) for window in windows)
    survived = sum(int(window.get("signals_survived") or 0) for window in windows)
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
        "max_drawdown_pct_worst": max(
            (float(window.get("max_drawdown_pct") or 0.0) for window in windows),
            default=None,
        ),
        "windows": windows,
    }


def row_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("decision_id") or ""),
            str(row.get("sleeve_key") or ""),
            str(row.get("ticker") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("exit_date") or ""),
        ]
    )


def load_forward_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_rows = read_jsonl(FORWARD_REPLACEMENT)
    deduped: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        deduped[row_key(row)] = row

    usable: list[dict[str, Any]] = []
    missing_required = 0
    for row in deduped.values():
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            missing_required += 1
            continue
        values = {field: as_float(row.get(field)) for field in REPLACEMENT_FIELDS}
        if any(value is None for value in values.values()):
            missing_required += 1
            continue
        if not row.get("entry_date") or not row.get("exit_date"):
            missing_required += 1
            continue
        cohort = "etf" if ticker in ETF_TICKERS else "stock"
        usable.append(
            {
                **row,
                **values,
                "ticker": ticker,
                "cohort": cohort,
                "entry_month": str(row.get("entry_date") or "")[:7],
            }
        )
    usable.sort(
        key=lambda item: (
            item["cohort"],
            str(item.get("entry_date") or ""),
            str(item.get("sleeve_key") or ""),
            str(item.get("ticker") or ""),
        )
    )
    cohort_counts = Counter(row["cohort"] for row in usable)
    return usable, {
        "source_artifact": repo_rel(FORWARD_REPLACEMENT),
        "raw_rows": len(raw_rows),
        "deduped_rows": len(deduped),
        "usable_rows": len(usable),
        "missing_required_rows": missing_required,
        "cohort_counts": dict(sorted(cohort_counts.items())),
        "etf_ticker_set": sorted(ETF_TICKERS),
        "artifact_not_mutated": True,
    }


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 10) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(key) or "unknown") for row in rows)
    denominator = len(rows) or 1
    return [
        {"key": value, "n": count, "row_share": round(count / denominator, 6)}
        for value, count in counts.most_common(limit)
    ]


def positive_concentration(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    by_ticker: dict[str, float] = defaultdict(float)
    by_sleeve: dict[str, float] = defaultdict(float)
    for row in rows:
        value = as_float(row.get(field))
        if value is None or value <= 0:
            continue
        by_ticker[str(row.get("ticker") or "unknown")] += value
        by_sleeve[str(row.get("sleeve_key") or "unknown")] += value
    total = sum(by_ticker.values())
    if total <= 0:
        return {
            "positive_total": 0.0,
            "max_single_ticker_positive_share": None,
            "max_single_sleeve_positive_share": None,
            "top_positive_tickers": [],
            "top_positive_sleeves": [],
        }
    return {
        "positive_total": round(total, 2),
        "max_single_ticker_positive_share": round(max(by_ticker.values()) / total, 6),
        "max_single_sleeve_positive_share": round(max(by_sleeve.values()) / total, 6),
        "top_positive_tickers": [
            {
                "ticker": ticker,
                "positive_value": round(value, 2),
                "share": round(value / total, 6),
            }
            for ticker, value in sorted(by_ticker.items(), key=lambda item: item[1], reverse=True)
        ],
        "top_positive_sleeves": [
            {
                "sleeve": sleeve,
                "positive_value": round(value, 2),
                "share": round(value / total, 6),
            }
            for sleeve, value in sorted(by_sleeve.items(), key=lambda item: item[1], reverse=True)
        ],
    }


def field_summary(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in rows if as_float(row.get(field)) is not None]
    return {
        "sum": round(sum(values), 2) if values else 0.0,
        "mean": round_or_none(mean(values), 4),
        "median": round_or_none(median(values), 4) if values else None,
        "min": round_or_none(min(values), 4) if values else None,
        "max": round_or_none(max(values), 4) if values else None,
        "positive_rate": round(sum(1 for value in values if value > 0) / len(values), 6)
        if values
        else None,
        "concentration": positive_concentration(rows, field),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "n": len(rows),
        "distinct_tickers": len({str(row.get("ticker") or "unknown") for row in rows}),
        "distinct_sleeves": len({str(row.get("sleeve_key") or "unknown") for row in rows}),
        "tickers": top_counts(rows, "ticker"),
        "sleeves": top_counts(rows, "sleeve_key"),
        "entry_months": top_counts(rows, "entry_month"),
        "notional_methods": top_counts(rows, "notional_method"),
    }
    for field in REPLACEMENT_FIELDS:
        summary[field] = field_summary(rows, field)
    return summary


def summarize_grouped(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return {value: summarize_rows(group) for value, group in sorted(grouped.items())}


def compare_stock_to_etf(stock: dict[str, Any], etf: dict[str, Any]) -> dict[str, Any]:
    by_field = {}
    wins = 0
    for field in REPLACEMENT_FIELDS:
        stock_mean = stock[field]["mean"]
        etf_mean = etf[field]["mean"]
        delta = None
        stock_beats = False
        if stock_mean is not None and etf_mean is not None:
            delta = round(stock_mean - etf_mean, 4)
            stock_beats = stock_mean > etf_mean
            wins += int(stock_beats)
        by_field[field] = {
            "stock_mean": stock_mean,
            "etf_mean": etf_mean,
            "stock_minus_etf_mean": delta,
            "stock_beats_etf_mean": stock_beats,
        }
    return {"by_field": by_field, "stock_mean_comparator_wins": wins}


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stock_rows = [row for row in rows if row["cohort"] == "stock"]
    etf_rows = [row for row in rows if row["cohort"] == "etf"]
    stock_summary = summarize_rows(stock_rows)
    etf_summary = summarize_rows(etf_rows)
    return {
        "all_rows": summarize_rows(rows),
        "cohorts": {
            "stock": stock_summary,
            "etf": etf_summary,
        },
        "stock_vs_etf": compare_stock_to_etf(stock_summary, etf_summary),
        "stock_by_sleeve": summarize_grouped(stock_rows, "sleeve_key"),
        "stock_by_entry_month": summarize_grouped(stock_rows, "entry_month"),
        "etf_by_sleeve": summarize_grouped(etf_rows, "sleeve_key"),
        "sample_rows": [
            {
                "cohort": row["cohort"],
                "sleeve_key": row.get("sleeve_key"),
                "ticker": row.get("ticker"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "replacement_value_vs_cash_usd": round_or_none(
                    row.get("replacement_value_vs_cash_usd"), 2
                ),
                "replacement_value_vs_spy_usd": round_or_none(
                    row.get("replacement_value_vs_spy_usd"), 2
                ),
                "replacement_value_vs_qqq_usd": round_or_none(
                    row.get("replacement_value_vs_qqq_usd"), 2
                ),
            }
            for row in rows[:12]
        ],
    }


def acceptance_checks(analysis: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    stock = analysis["cohorts"]["stock"]
    comparison = analysis["stock_vs_etf"]
    concentration = stock["replacement_value_vs_cash_usd"]["concentration"]
    max_ticker_share = concentration["max_single_ticker_positive_share"]
    all_totals_positive = all(stock[field]["sum"] > 0 for field in REPLACEMENT_FIELDS)
    all_medians_positive = all((stock[field]["median"] or 0.0) > 0 for field in REPLACEMENT_FIELDS)
    checks = {
        "stock_rows_passed": stock["n"] >= CONFIG["min_stock_rows"],
        "stock_distinct_tickers_passed": (
            stock["distinct_tickers"] >= CONFIG["min_distinct_stock_tickers"]
        ),
        "stock_total_positive_all_comparators": all_totals_positive,
        "stock_median_positive_all_comparators": all_medians_positive,
        "stock_cash_positive_concentration_passed": (
            max_ticker_share is not None
            and max_ticker_share <= CONFIG["max_single_ticker_positive_cash_share"]
        ),
        "stock_mean_beats_etf_two_comparators": (
            comparison["stock_mean_comparator_wins"]
            >= CONFIG["min_stock_mean_comparator_wins"]
        ),
    }
    failed = [key for key, passed in checks.items() if not passed]
    return checks, failed


def calibration(prediction: dict[str, Any], success: bool, failed: list[str]) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if success else 0.0
    observed_modes = []
    if "stock_rows_passed" in failed:
        observed_modes.append("stock rows too few")
    if "stock_cash_positive_concentration_passed" in failed:
        observed_modes.append("stock replacement value dominated by one ticker")
    if "stock_mean_beats_etf_two_comparators" in failed:
        observed_modes.append("ETF rows explain most value")
    if (
        "stock_total_positive_all_comparators" in failed
        or "stock_median_positive_all_comparators" in failed
    ):
        observed_modes.append("benchmark-adjusted replacement value negative")
    declared = set(prediction.get("main_failure_modes") or [])
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": int(actual),
        "brier_score": round((probability - actual) ** 2, 6),
        "failed_reasons": failed,
        "failure_modes_observed": observed_modes,
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "predicted_failure_mode_hit": bool(declared & set(observed_modes)),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = load_baseline_metrics()
    rows, source_audit = load_forward_rows()
    analysis = analyze(rows)
    checks, failed = acceptance_checks(analysis)
    observed_lead = not failed
    status = "observed_only_positive_lead" if observed_lead else "observed_only_rejected"
    decision = (
        "observed_only_stock_forward_replacement_value_positive_not_promoted"
        if observed_lead
        else "rejected_stock_forward_replacement_attribution_not_activation_ready"
    )
    why = (
        "The stock-only cohort passed the fixed composition checks, but this "
        "remains a read-only forward attribution without a shared helper, daily "
        "snapshot, or activation envelope."
        if observed_lead
        else "The stock-only cohort did not pass the fixed composition checks, "
        "so current forward replacement evidence remains insufficient for "
        "activation and should not be treated as diversified stock alpha."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "lane": "alpha_search",
        "owner": OWNER,
        "decision": decision,
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
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation novelty gate reported no strong "
                    "near-neighbor. Nearby priors were explicitly declared as "
                    "forward replacement readiness, current-surface readiness, "
                    "and regime-scalar attribution."
                ),
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            },
            "3_single_policy_bundle": (
                "One read-only attribution bundle: split enriched closed "
                "forward replacement rows into stock versus ETF cohorts and "
                "score cash/SPY/QQQ replacement value plus concentration."
            ),
            "4_success_failure_standard": (
                "Observed-only positive lead only if stock-only rows have "
                "positive total and median replacement value versus cash, SPY, "
                "and QQQ; at least 15 rows; at least 8 distinct tickers; no "
                "single ticker over 50% of positive cash value; and stock mean "
                "beats ETF mean on at least two comparators."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "source_artifact": repo_rel(FORWARD_REPLACEMENT),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "config": CONFIG,
            "etf_ticker_set": sorted(ETF_TICKERS),
            "replacement_fields": REPLACEMENT_FIELDS,
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
            "note": "Observed-only attribution; before and after policy are identical.",
        },
        "gate2": {
            "dependencies_validated": bool(rows),
            "source_audit": source_audit,
            "fields_checked": [
                "entry_date",
                "exit_date",
                "ticker",
                "sleeve_key",
                "notional_usd",
                "notional_method",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in rows),
            "target_price_relevance": (
                "Not applicable: no executable entry, target, exit, order, or "
                "paper ledger mutation is scheduled by this observed-only "
                "attribution."
            ),
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": source_audit["deduped_rows"],
            "signals_survived": source_audit["usable_rows"],
            "survival_rate": round(source_audit["usable_rows"] / source_audit["deduped_rows"], 4)
            if source_audit["deduped_rows"]
            else None,
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; rows are attributed only.",
        },
        "gate4": {
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
                "Forward-only closed paper rows, not canonical fixed-window alpha evidence.",
                "No shared helper, daily adapter, rank, notional, exit, or order rule changed.",
                "Any activation requires a separate shared-paper-first Gate 1-4 experiment.",
            ],
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "attribution": {
            "analysis": analysis,
            "source_audit": source_audit,
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
            "parity_note": "Read-only attribution over existing forward replacement artifact.",
        },
        "calibration": calibration(prediction, observed_lead, failed),
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing ETF ticker set, minimum rows, ticker "
                "count, concentration cap, comparator count, sleeve inclusion, "
                "notional method, hold days, or activation thresholds on the "
                "same forward replacement rows."
            ),
            "new_evidence_required": (
                "Need materially more closed forward rows from default-off "
                "paper sleeves, or a separate shared helper that generates "
                "fresh stock-diversified forward evidence, before any activation "
                "or allocation test."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(FORWARD_REPLACEMENT),
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260622-013.json",
            "experiments/logs/exp-20260623-019.json",
            "experiments/logs/exp-20260623-027.json",
            "docs/backtesting.md",
            "docs/production_backtest_parity.md",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["attribution"]["analysis"]
    return {
        "experiment_id": payload["experiment_id"],
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
        "attribution": {
            "all_rows": analysis["all_rows"],
            "cohorts": analysis["cohorts"],
            "stock_vs_etf": analysis["stock_vs_etf"],
            "stock_by_sleeve": analysis["stock_by_sleeve"],
            "stock_by_entry_month": analysis["stock_by_entry_month"],
        },
        "production_impact": payload["production_impact"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "anti_js": payload["anti_js"],
    }


def money(value: Any) -> str:
    number = as_float(value)
    return "n/a" if number is None else f"${number:,.2f}"


def build_card(payload: dict[str, Any]) -> str:
    analysis = payload["attribution"]["analysis"]
    stock = analysis["cohorts"]["stock"]
    etf = analysis["cohorts"]["etf"]
    comparison = analysis["stock_vs_etf"]["by_field"]
    rows = [
        "| Comparator | Stock Sum | Stock Mean | Stock Median | ETF Mean | Stock-ETF Mean |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field in REPLACEMENT_FIELDS:
        rows.append(
            "| {field} | {stock_sum} | {stock_mean} | {stock_median} | {etf_mean} | {delta} |".format(
                field=field,
                stock_sum=money(stock[field]["sum"]),
                stock_mean=money(stock[field]["mean"]),
                stock_median=money(stock[field]["median"]),
                etf_mean=money(etf[field]["mean"]),
                delta=money(comparison[field]["stock_minus_etf_mean"]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: stock vs ETF forward replacement attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            "- Shared helper promoted: `false`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Cohort Summary",
            "",
            f"- Stock rows: `{stock['n']}` across `{stock['distinct_tickers']}` tickers and `{stock['distinct_sleeves']}` sleeves",
            f"- ETF rows: `{etf['n']}` across `{etf['distinct_tickers']}` tickers and `{etf['distinct_sleeves']}` sleeves",
            f"- Stock mean comparator wins: `{analysis['stock_vs_etf']['stock_mean_comparator_wins']}`",
            f"- Max single stock ticker positive cash share: `{stock['replacement_value_vs_cash_usd']['concentration']['max_single_ticker_positive_share']}`",
            "",
            "## Replacement Value",
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
        FORWARD_REPLACEMENT,
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
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in files},
        "anti_js": payload["anti_js"],
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
        "calibration": payload["calibration"],
        "attribution": {
            "cohorts": payload["attribution"]["analysis"]["cohorts"],
            "stock_vs_etf": payload["attribution"]["analysis"]["stock_vs_etf"],
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
            "hypothesis": payload["hypothesis"],
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
    stock = analysis["cohorts"]["stock"]
    etf = analysis["cohorts"]["etf"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "stock_rows": stock["n"],
                "stock_distinct_tickers": stock["distinct_tickers"],
                "etf_rows": etf["n"],
                "stock_cash_sum": stock["replacement_value_vs_cash_usd"]["sum"],
                "stock_spy_sum": stock["replacement_value_vs_spy_usd"]["sum"],
                "stock_qqq_sum": stock["replacement_value_vs_qqq_usd"]["sum"],
                "stock_mean_comparator_wins": analysis["stock_vs_etf"][
                    "stock_mean_comparator_wins"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
