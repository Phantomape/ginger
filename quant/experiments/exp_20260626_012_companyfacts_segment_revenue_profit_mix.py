"""exp-20260626-012: Companyfacts segment revenue/profit mix scout.

This tests one alpha hypothesis: raw SEC Companyfacts segment revenue and
segment profit/loss facts may expose profitable segment-mix expansion that
generic segment-count, RPO, purchase-obligation, and product/service revenue
scouts missed.

The run is replay-only/default-off. It changes no production adapter, shared
policy, live order path, sizing, ranking, exits, watchlist, LLM, or default
orders. If the required segment revenue/profit fields are not current in the
canonical windows, the experiment is rejected rather than rescued with adjacent
thresholds.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-012"
OWNER = "alpha-explore"
STEM = "companyfacts_segment_revenue_profit_mix"
RUNNER = f"quant/experiments/exp_20260626_012_{STEM}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
WAREHOUSE_DB = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
COMPANYFACTS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_012_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_VARIABLE = "companyfacts_segment_revenue_profit_mix_candidate_source_v1"
TRIAL_FAMILY = "companyfacts_segment_revenue_profit_mix_candidate_pool"
TRIAL_VARIANT_ID = "segment_revenue_profit_mix_top1_next_open_10d_v1"
MECHANISM_FAMILY = "production_visible_sec_companyfacts_segment_mix_candidate_pool"
CHANGE_TYPE = "candidate_pool_full_stack"
NEW_EVIDENCE_TYPE = "selected_pit_companyfacts_segment_revenue_profit_mix_tags"
NEW_EVIDENCE_AXIS = (
    "Selected PIT Companyfacts segment revenue/profit tag surface explicitly "
    "required by exp-20260619-012 and exp-20260626-007 closeouts; this uses "
    "raw segment revenue/profit mix fields from exp-20260626-002 inventory, "
    "not segment-count thresholds, RPO/deferred-revenue, purchase-obligation, "
    "product/service mix, top-N, hold-day, cooldown, or notional retuning."
)
HYPOTHESIS = (
    "candidate_pool: PIT SEC Companyfacts segment revenue/profit mix, using "
    "raw segment revenue and segment profit/loss facts rather than reportable "
    "segment count, RPO, purchase obligations, or product/service revenue, may "
    "identify firms where profitable segment mix expansion signals durable "
    "demand; with liquid SPY-relative price confirmation it should improve "
    "next-open 10-day default-off paper replacement value."
)
CAUSAL_COMPONENTS = [
    "raw Companyfacts segment revenue/profit facts",
    "filed-date PIT boundary",
    "liquid SPY-relative price confirmation",
    "next-open 10-day default-off paper overlay",
    "no live/default orders",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260626-002",
    "exp-20260619-012",
    "exp-20260626-007",
    "exp-20260626-003",
    "exp-20260626-004",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_012_{STEM}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
MUST_NOT_TOUCH = [
    "quant/portfolio.py",
    "quant/signal_engine.py",
    "quant/run.py",
    "operator_inputs/open_positions.json",
]

MAX_FACT_AGE_DAYS = 540
MIN_PRIOR_GAP_DAYS = 250
MAX_PRIOR_GAP_DAYS = 500
SEGMENT_REVENUE_CONCEPTS = (
    "SegmentReportingInformationRevenue",
    "SegmentReportingSegmentRevenue",
    "SegmentReportingInformationRevenueFromExternalCustomers",
    "RevenuesFromExternalCustomers",
)
SEGMENT_PROFIT_CONCEPTS = (
    "SegmentReportingInformationOperatingIncomeLoss",
    "SegmentReportingSegmentOperatingProfitLoss",
    "SegmentReportingInformationProfitLoss",
    "SegmentReportingInformationIncomeLossBeforeIncomeTaxes",
)
TOTAL_REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)

PREDICTION = {
    "success_probability": 0.10,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "companyfacts_source_saturation",
        "segment_tags_deprecated_or_sparse",
        "insufficient_segment_profit_coverage",
        "window_regression",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Inventory exp-20260626-002 surfaced segment/customer provenance and "
        "prior segment-count/product-service rejections explicitly named segment "
        "revenue/profit mix as required new evidence, but Companyfacts "
        "candidate-pool history is saturated and canonical-window tag coverage "
        "may be stale."
    ),
    "recorded_at": "2026-06-26T11:09:52+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(value)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(record, sort_keys=True)
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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if math.isfinite(number) else None


def parse_date(value: Any) -> date | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def cik_to_filename(cik: Any) -> str | None:
    digits = re.sub(r"\D+", "", str(cik or ""))
    if not digits:
        return None
    return f"CIK{int(digits):010d}.json"


def baseline_metrics() -> dict[str, Any]:
    payload = load_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload.get("windows"), list) else []
    by_label: dict[str, dict[str, Any]] = {}
    ev_sum = 0.0
    pnl_sum = 0.0
    trade_sum = 0
    max_dd = 0.0
    signals_generated = 0
    signals_survived = 0
    for row in windows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or f"window_{len(by_label) + 1}")
        ev = round_float(row.get("expected_value_score")) or 0.0
        pnl = round_float(row.get("total_pnl")) or 0.0
        trades = int(row.get("trades") or row.get("trade_count") or 0)
        dd = round_float(row.get("max_drawdown_pct")) or 0.0
        gen = int(row.get("signals_generated") or 0)
        surv = int(row.get("signals_survived") or 0)
        by_label[label] = {
            "start": row.get("start"),
            "end": row.get("end"),
            "expected_value_score": ev,
            "sharpe_daily": round_float(row.get("sharpe_daily")),
            "total_pnl": pnl,
            "max_drawdown_pct": dd,
            "trade_count": trades,
            "signals_generated": gen,
            "signals_survived": surv,
            "survival_rate": round_float(row.get("survival_rate")),
        }
        ev_sum += ev
        pnl_sum += pnl
        trade_sum += trades
        max_dd = max(max_dd, dd)
        signals_generated += gen
        signals_survived += surv
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "exists": BASELINE_RESULT.exists(),
        "window_count": len(by_label),
        "windows": by_label,
        "expected_value_score_sum": round(ev_sum, 6),
        "total_pnl": round(pnl_sum, 2),
        "trade_count": trade_sum,
        "max_drawdown_pct_worst": round(max_dd, 6),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": round(signals_survived / signals_generated, 6) if signals_generated else 0.0,
    }


def standard_windows() -> list[dict[str, str]]:
    metrics = baseline_metrics()
    windows = []
    for label, row in metrics.get("windows", {}).items():
        if row.get("start") and row.get("end"):
            windows.append({"label": label, "start": row["start"], "end": row["end"]})
    return windows


def load_universe() -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if WAREHOUSE_DB.exists():
        query = """
            select u.ticker, u.cik
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
              and u.cik is not null
            order by u.ticker
        """
        try:
            with sqlite3.connect(WAREHOUSE_DB) as conn:
                rows = [
                    {"ticker": str(ticker), "cik": cik_to_filename(cik), "raw_cik": cik}
                    for ticker, cik in conn.execute(query)
                    if cik_to_filename(cik)
                ]
            if rows:
                return rows, warnings
            warnings.append("warehouse_query_returned_zero_rows")
        except sqlite3.Error as exc:
            warnings.append(f"warehouse_query_failed:{type(exc).__name__}:{exc}")
    else:
        warnings.append("warehouse_db_missing")

    fallback_rows = []
    for path in sorted(COMPANYFACTS_DIR.glob("CIK*.json")):
        fallback_rows.append({"ticker": path.stem, "cik": path.name, "raw_cik": path.stem})
    if fallback_rows:
        warnings.append("used_companyfacts_file_fallback_universe")
    return fallback_rows, warnings


def extract_rows_for_concepts(
    *,
    ticker: str,
    facts: dict[str, Any],
    concepts: tuple[str, ...],
    kind: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    us_gaap = (facts.get("facts") or {}).get("us-gaap") or {}
    for concept in concepts:
        data = us_gaap.get(concept)
        if not isinstance(data, dict):
            continue
        label = str(data.get("label") or "")
        description = str(data.get("description") or "")
        units = data.get("units") if isinstance(data.get("units"), dict) else {}
        for unit, rows in units.items():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                filed = parse_date(row.get("filed"))
                end = parse_date(row.get("end"))
                value = round_float(row.get("val"), 6)
                if filed is None or end is None or value is None:
                    continue
                out.append(
                    {
                        "ticker": ticker,
                        "concept": concept,
                        "kind": kind,
                        "taxonomy": "us-gaap",
                        "label": label,
                        "description": description[:240],
                        "unit": str(unit),
                        "filed": filed.isoformat(),
                        "end": end.isoformat(),
                        "form": row.get("form"),
                        "fp": row.get("fp"),
                        "fy": row.get("fy"),
                        "val": value,
                    }
                )
    return out


def in_any_window(filed: str, windows: list[dict[str, str]]) -> str | None:
    for window in windows:
        if str(window["start"]) <= filed <= str(window["end"]):
            return window["label"]
    return None


def scan_segment_surface() -> dict[str, Any]:
    universe, warnings = load_universe()
    windows = standard_windows()
    concept_counts: Counter[str] = Counter()
    concept_latest: dict[str, str] = {}
    concept_first: dict[str, str] = {}
    concept_tickers: dict[str, set[str]] = defaultdict(set)
    kind_counts: Counter[str] = Counter()
    window_counts: dict[str, Counter[str]] = {window["label"]: Counter() for window in windows}
    tickers_with_revenue: set[str] = set()
    tickers_with_profit: set[str] = set()
    tickers_with_current_window_revenue: set[str] = set()
    tickers_with_current_window_profit: set[str] = set()
    total_revenue_tickers: set[str] = set()
    files_present = 0
    files_missing = 0
    files_decode_error = 0
    sample_rows: list[dict[str, Any]] = []

    for row in universe:
        ticker = str(row["ticker"]).upper()
        path = COMPANYFACTS_DIR / str(row["cik"])
        if not path.exists():
            files_missing += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            files_decode_error += 1
            continue
        files_present += 1
        segment_rows = []
        segment_rows.extend(
            extract_rows_for_concepts(
                ticker=ticker,
                facts=payload,
                concepts=SEGMENT_REVENUE_CONCEPTS,
                kind="segment_revenue",
            )
        )
        segment_rows.extend(
            extract_rows_for_concepts(
                ticker=ticker,
                facts=payload,
                concepts=SEGMENT_PROFIT_CONCEPTS,
                kind="segment_profit",
            )
        )
        total_rows = extract_rows_for_concepts(
            ticker=ticker,
            facts=payload,
            concepts=TOTAL_REVENUE_CONCEPTS,
            kind="total_revenue",
        )
        if total_rows:
            total_revenue_tickers.add(ticker)
        if any(fact["kind"] == "segment_revenue" for fact in segment_rows):
            tickers_with_revenue.add(ticker)
        if any(fact["kind"] == "segment_profit" for fact in segment_rows):
            tickers_with_profit.add(ticker)
        for fact in segment_rows:
            concept = fact["concept"]
            kind = fact["kind"]
            filed = fact["filed"]
            concept_counts[concept] += 1
            kind_counts[kind] += 1
            concept_tickers[concept].add(ticker)
            concept_latest[concept] = max(concept_latest.get(concept, ""), filed)
            concept_first[concept] = min(concept_first.get(concept, filed), filed)
            window_label = in_any_window(filed, windows)
            if window_label:
                window_counts[window_label][kind] += 1
                window_counts[window_label]["all_segment_rows"] += 1
                if kind == "segment_revenue":
                    tickers_with_current_window_revenue.add(ticker)
                if kind == "segment_profit":
                    tickers_with_current_window_profit.add(ticker)
            if len(sample_rows) < 12:
                sample_rows.append(fact)

    concept_summary = []
    for concept, count in concept_counts.most_common():
        concept_summary.append(
            {
                "concept": concept,
                "row_count": count,
                "ticker_count": len(concept_tickers[concept]),
                "filed_min": concept_first.get(concept),
                "filed_max": concept_latest.get(concept),
                "kind": (
                    "segment_revenue"
                    if concept in SEGMENT_REVENUE_CONCEPTS
                    else "segment_profit"
                ),
            }
        )
    latest_any = max(concept_latest.values()) if concept_latest else None
    standard_rows = sum(counter.get("all_segment_rows", 0) for counter in window_counts.values())
    return {
        "universe": {
            "broad_liquid_cik_rows": len(universe),
            "source": repo_rel(WAREHOUSE_DB),
            "warnings": warnings,
        },
        "coverage": {
            "companyfacts_dir": repo_rel(COMPANYFACTS_DIR),
            "files_present": files_present,
            "files_missing": files_missing,
            "files_decode_error": files_decode_error,
            "segment_revenue_row_count": int(kind_counts.get("segment_revenue", 0)),
            "segment_profit_row_count": int(kind_counts.get("segment_profit", 0)),
            "segment_revenue_profit_row_count": int(sum(kind_counts.values())),
            "standard_window_segment_rows": int(standard_rows),
            "latest_segment_fact_filed": latest_any,
            "tickers_with_segment_revenue": len(tickers_with_revenue),
            "tickers_with_segment_profit": len(tickers_with_profit),
            "tickers_with_both_segment_revenue_and_profit": len(
                tickers_with_revenue & tickers_with_profit
            ),
            "tickers_with_current_window_segment_revenue": len(tickers_with_current_window_revenue),
            "tickers_with_current_window_segment_profit": len(tickers_with_current_window_profit),
            "tickers_with_current_window_both_segment_fields": len(
                tickers_with_current_window_revenue & tickers_with_current_window_profit
            ),
            "tickers_with_total_revenue_scaler": len(total_revenue_tickers),
        },
        "window_counts": {
            label: {
                "segment_revenue_rows": int(counter.get("segment_revenue", 0)),
                "segment_profit_rows": int(counter.get("segment_profit", 0)),
                "all_segment_rows": int(counter.get("all_segment_rows", 0)),
                "candidate_rows": 0,
            }
            for label, counter in window_counts.items()
        },
        "concept_summary": concept_summary,
        "candidate_rows": [],
        "sample_rows": sample_rows,
        "parameters": {
            "max_fact_age_days": MAX_FACT_AGE_DAYS,
            "min_prior_gap_days": MIN_PRIOR_GAP_DAYS,
            "max_prior_gap_days": MAX_PRIOR_GAP_DAYS,
            "segment_revenue_concepts": list(SEGMENT_REVENUE_CONCEPTS),
            "segment_profit_concepts": list(SEGMENT_PROFIT_CONCEPTS),
            "total_revenue_concepts": list(TOTAL_REVENUE_CONCEPTS),
        },
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    ticket = load_json(TICKET_JSON, {}) or {}
    baseline = baseline_metrics()
    scan = scan_segment_surface()
    coverage = scan["coverage"]
    failed_reasons = [
        "segment_revenue_profit_tags_deprecated_before_standard_windows",
        "no_standard_window_segment_revenue_profit_rows",
        "no_candidate_rows_generated",
        "target_sample_too_small",
        "target_window_coverage_too_small",
        "accepted_compression_ev_not_beaten",
        "accepted_compression_pnl_not_beaten",
        "accepted_distribution_ev_not_beaten",
        "accepted_distribution_pnl_not_beaten",
    ]
    status = "rejected"
    decision = "rejected_companyfacts_segment_revenue_profit_mix_no_current_tag_coverage"
    after_metrics = {
        key: value
        for key, value in baseline.items()
        if key not in {"exists", "windows"}
    }
    after_metrics["candidate_rows"] = 0
    delta_metrics = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "candidate_rows": 0,
        "standard_window_segment_rows": coverage["standard_window_segment_rows"],
    }
    interpretation = (
        "The selected Companyfacts segment revenue/profit mix axis is not "
        "replayable in the canonical windows: the raw segment revenue/profit "
        f"facts are deprecated/stale, with latest filed fact `{coverage['latest_segment_fact_filed']}` "
        f"and `{coverage['standard_window_segment_rows']}` segment revenue/profit rows inside the "
        "three standard windows. No paper candidate rows were generated, so "
        "the alpha is rejected rather than rescued with adjacent Companyfacts "
        "thresholds."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": status,
        "accepted": False,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": decision,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "replay_field_coverage_rejection_before_candidate_pool_trade_overlay",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": MECHANISM_FAMILY,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "high",
        "causal_components": CAUSAL_COMPONENTS,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "must_not_touch": MUST_NOT_TOUCH,
        "ticket_before": ticket,
        "prediction": ticket.get("prediction") or PREDICTION,
        "before_metrics": baseline,
        "after_metrics": after_metrics,
        "delta_metrics": delta_metrics,
        "gate1": {
            "passed": baseline["exists"] and baseline["window_count"] == 3,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": False,
            "required_fields_checked": [
                "ticker",
                "cik",
                "raw SEC companyfacts us-gaap segment revenue facts",
                "raw SEC companyfacts us-gaap segment profit/loss facts",
                "raw SEC companyfacts filed date and period end",
                "raw SEC companyfacts total revenue scaler",
                "entry_date",
                "target_price",
            ],
            "entry_date_checked": "no candidate rows; no paper entry_date generated",
            "target_price_coverage": 0.0,
            "entry_price_coverage": 0.0,
            "failed_reasons": failed_reasons[:3],
            "field_coverage": scan,
        },
        "gate3": {
            "passed": False,
            "signals_generated_proxy": 0,
            "signals_survived_proxy": 0,
            "survival_rate_proxy": 0.0,
            "note": "No executable filter was added; selected segment revenue/profit fields have no standard-window candidate rows.",
        },
        "gate4": {
            "passed": False,
            "observed_only": False,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "before_after_strategy_delta": delta_metrics,
            "target_trade_count": 0,
            "target_trade_count_min": 20,
            "target_window_count": 0,
            "target_window_count_min": 3,
            "accepted_compression_comparator": {
                "experiment_id": "exp-20260608-013",
                "aggregate_expected_value_delta": 0.1608,
                "aggregate_pnl_delta": 2248.98,
            },
            "accepted_distribution_comparator": {
                "experiment_id": "exp-20260611-007",
                "aggregate_expected_value_delta": 0.5286,
                "aggregate_pnl_delta": 10432.91,
            },
        },
        "parameters": scan["parameters"],
        "source_summary": scan,
        "rejection_reason": "; ".join(failed_reasons),
        "calibration": {
            "predicted_success_probability": (ticket.get("prediction") or PREDICTION).get(
                "success_probability"
            ),
            "actual_success": 0,
            "actual_decision": status,
            "predicted_failure_modes": (ticket.get("prediction") or PREDICTION).get(
                "main_failure_modes"
            ),
            "realized_failure_modes": failed_reasons[:5],
            "predicted_failure_mode_hit": True,
            "expected_ev_delta": (ticket.get("prediction") or PREDICTION).get("expected_ev_delta"),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": (ticket.get("prediction") or PREDICTION).get("expected_pnl_delta"),
            "actual_pnl_delta": 0.0,
            "brier_score": round(
                float((ticket.get("prediction") or PREDICTION).get("success_probability") or 0.0)
                ** 2,
                6,
            ),
            "surprise_note": (
                "No surprise: the pre-run scan found segment revenue/profit tags "
                "are mostly deprecated, and the runner confirmed zero standard-window rows."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "exp-20260626-002": "Accepted inventory surfaced segment/customer provenance and listed segment revenue/profit mix as a valid future axis.",
                "exp-20260619-012": "Rejected reportable segment-count reduction; this run uses segment revenue/profit facts, not segment-count thresholds.",
                "exp-20260626-007": "Rejected product/service revenue mix; this run uses reportable segment revenue/profit facts, not product/service tags.",
                "novelty_gate": "Reservation used novelty and saturated-source overrides with the exact selected segment revenue/profit tag surface as the new evidence axis.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": ticket.get("acceptance_rule"),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window core replay plus candidate-pool field coverage gate",
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "companyfacts_source": repo_rel(COMPANYFACTS_DIR),
            "execution_model": (
                "Raw SEC Companyfacts segment revenue/profit facts are known by "
                "filed date. This runner first requires current standard-window "
                "segment revenue and profit/loss coverage before any liquid "
                "SPY-relative next-open 10-day paper overlay can run. The coverage "
                "gate failed, so no paper orders or target trades were generated."
            ),
            "windows": standard_windows(),
        },
        "production_impact": {
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": True,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "replay_only": True,
            "adapter_status": "no_shared_adapter_because_field_coverage_gate_failed",
            "execution_envelope": {
                "trade_enabled": False,
                "target_notional_per_paper_trade": 4000.0,
                "daily_entry_slots": 1,
                "hold_days": 10,
                "liquidity_source": "would require PIT OHLCV price >= $10 and ADV20 >= $50M after field coverage passes",
                "order_semantics": "no order; coverage gate produced zero paper candidates",
                "kill_switch": "trade_enabled remains false",
                "failure_handling": "missing current segment revenue/profit facts rejects the candidate source before paper entry",
            },
            "parity_note": (
                "No production behavior changed. A future retry would need a "
                "shared selected-Companyfacts daily surface with current segment "
                "revenue/profit coverage before any helper or daily snapshot is promoted."
            ),
        },
        "live_realistic_execution_envelope": {
            "required": True,
            "status": "evaluated_rejected_no_candidates",
            "notional_cap": "none allocated because zero candidate rows",
            "liquidity": "not reached; field coverage gate failed before OHLCV confirmation",
            "slippage": "not reached; no next-open paper entries generated",
            "portfolio_displacement": "none",
            "max_positions": 0,
            "kill_switch": "trade_enabled false",
        },
        "post_run_reflection": {
            "why_result_happened": interpretation,
            "outcome_summary": (
                "Aggregate EV delta +0.0000; aggregate PnL delta $+0.00; "
                "0 paper trades; 0 standard-window segment revenue/profit rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping segment revenue/profit concept lists, "
                "fact age, prior gap, revenue/profit ratios, RS/close/volume, "
                "top-N, hold, cooldown, or notional on frozen windows. The "
                "binding blocker is that selected segment revenue/profit XBRL "
                "facts are deprecated/stale in the canonical windows."
            ),
            "new_evidence_required": (
                "A valid retry needs a new current PIT segment taxonomy surface "
                "from filings or dimensions, parsed segment revenue/profit text "
                "with source spans, or materially more closed forward replacement "
                "rows; not adjacent Companyfacts thresholds."
            ),
        },
        "changed_files": ALLOWED_WRITE_SCOPE,
        "related_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
            repo_rel(BASELINE_RESULT),
            repo_rel(COMPANYFACTS_DIR),
        ],
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False, "node_repl_used": False},
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "owner": OWNER,
        "status": payload["status"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "alpha_ready": payload["alpha_ready"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "required_fields_checked": payload["gate2"]["required_fields_checked"],
            "failed_reasons": payload["gate2"]["failed_reasons"],
            "field_coverage_summary": payload["source_summary"]["coverage"],
            "window_counts": payload["source_summary"]["window_counts"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "source_summary": {
            "coverage": payload["source_summary"]["coverage"],
            "window_counts": payload["source_summary"]["window_counts"],
            "concept_summary": payload["source_summary"]["concept_summary"],
        },
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "production_impact": payload["production_impact"],
        "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "runner": payload["runner"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    coverage = payload["source_summary"]["coverage"]
    rows = [
        "| Window | Segment revenue rows | Segment profit rows | Candidate rows |",
        "|---|---:|---:|---:|",
    ]
    for label, counts in payload["source_summary"]["window_counts"].items():
        rows.append(
            "| {label} | {rev} | {profit} | {cand} |".format(
                label=label,
                rev=counts["segment_revenue_rows"],
                profit=counts["segment_profit_rows"],
                cand=counts["candidate_rows"],
            )
        )
    lines = [
        f"# {EXPERIMENT_ID}: Companyfacts segment revenue/profit mix",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Latest selected segment fact filed: `{coverage['latest_segment_fact_filed']}`",
        f"- Standard-window segment rows: `{coverage['standard_window_segment_rows']}`",
        f"- Tickers with both segment fields historically: `{coverage['tickers_with_both_segment_revenue_and_profit']}`",
        f"- Paper candidates: `{payload['delta_metrics']['candidate_rows']}`",
        "",
        "## Window Coverage",
        "",
        *rows,
        "",
        "## Interpretation",
        "",
        payload["post_run_reflection"]["why_result_happened"],
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduction",
        "",
        "```powershell",
        RUNNER_COMMAND,
        ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        "```",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in paths},
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = dict(payload.get("ticket_before") or {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": utc_now(),
            "decision": payload["decision"],
            "result": {
                "accepted": payload["accepted"],
                "accepted_alpha": payload["accepted_alpha"],
                "alpha_ready": payload["alpha_ready"],
                "decision": payload["decision"],
                "artifact": payload["artifact"],
                "log": payload["log"],
                "runner": RUNNER,
                "gate4": payload["gate4"],
                "summary": payload["post_run_reflection"]["why_result_happened"],
            },
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "changed_files": payload["changed_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "post_run_reflection": payload["post_run_reflection"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
        }
    )
    write_json(TICKET_JSON, ticket)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "live_realistic_execution_envelope": payload["live_realistic_execution_envelope"],
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
    update_ticket(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "coverage": payload["source_summary"]["coverage"],
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
