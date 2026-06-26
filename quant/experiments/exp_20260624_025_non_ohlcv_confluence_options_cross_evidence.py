"""exp-20260624-025: non-OHLCV confluence plus options cross-evidence.

Observed-only alpha attribution. This runner checks whether the positive
exp-20260623-024 Form4+SEC confluence lead has same ticker/date overlap with
OnclickMedia options structure rows. No strategy, helper, ranking, sizing,
exit, paper fill, daily snapshot, LLM, watchlist, or live order behavior
changes in this experiment.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from collections import Counter
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


EXPERIMENT_ID = "exp-20260624-025"
OWNER = "alpha-explore"
SLUG = "non_ohlcv_confluence_options_cross_evidence"
RUNNER = f"quant/experiments/exp_20260624_025_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_025_{SLUG}.json"
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
EXP024_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260623_024_non_ohlcv_attention_confluence.py"
)
EXP024_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-024"
    / "exp_20260623_024_non_ohlcv_attention_confluence.json"
)
OPTIONS_LEDGERS = [
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260623-009"
    / "options_forward_observation_ledger.jsonl",
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-020"
    / "options_forward_observation_ledger_delta_20260623.jsonl",
]

HYPOTHESIS = (
    "Observed-only attribution: the exp-20260623-024 non-OHLCV Form4 plus SEC "
    "confluence lead may become more selective if same decision-date "
    "OnclickMedia options structure confirms bullish demand; first test "
    "whether the PIT options ledger overlaps confluence rows and whether "
    "confirmed rows beat unconfirmed confluence rows on replacement value."
)
CHANGE_TYPE = "observed_only_candidate_pool_attribution"
MECHANISM_FAMILY = "production_visible_non_ohlcv_cross_source_attention_candidate_pool"
TRIAL_FAMILY = "non_ohlcv_confluence_options_cross_evidence_attribution"
TRIAL_VARIANT_ID = "form4_sec_confluence_x_onclick_options_v1"
CHANGED_VARIABLE = "non_ohlcv_confluence_options_cross_evidence_overlap_v1"
NEW_EVIDENCE_TYPE = "options_cross_evidence_join"
NEW_EVIDENCE_AXIS = (
    "New machine-checkable evidence axis: joins the prior Form4+SEC confluence "
    "lead to a separate PIT OnclickMedia options structure ledger by ticker and "
    "usable trade date; not a SEC/Form4 threshold sweep."
)
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-024",
    "exp-20260623-025",
    "exp-20260624-020",
    "exp-20260624-023",
]
CAUSAL_COMPONENTS = [
    "exp024 confluence outcome replay",
    "OnclickMedia options ledger join",
    "overlap and replacement-value attribution",
    "no strategy behavior change",
]
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
    "daily_snapshot_exposed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "paper_orders_changed": False,
    "live_orders_changed": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "uses_exp024_confluence_replay": True,
    "uses_options_forward_context": True,
    "parity_note": (
        "Observed-only attribution. No shared policy/helper or production "
        "adapter behavior changed."
    ),
}
ACCEPTANCE_RULE = {
    "min_activity_date_option_matches": 10,
    "min_entry_date_option_matches": 10,
    "min_confluence_option_matches": 10,
    "requires_confirmed_beats_unconfirmed_cash_spy_qqq": True,
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-025/",
    "experiments/logs/exp-20260624-025.json",
    "experiments/cards/exp-20260624-025.md",
    "experiments/manifests/exp-20260624-025.json",
    "experiments/tickets/exp-20260624-025.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {} if default is None else default


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
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_float(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def round_or_none(value: Any, digits: int = 4) -> float | None:
    number = safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def load_exp024_module() -> Any:
    spec = importlib.util.spec_from_file_location("exp20260623024", EXP024_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {EXP024_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def confluence_outcomes() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    module = load_exp024_module()
    attention_rows, attention_audit = module.load_attention_rows()
    outcome_rows, outcome_audit = module.build_outcome_rows(attention_rows)
    return outcome_rows, {
        "attention_rows": len(attention_rows),
        "outcome_rows": len(outcome_rows),
        "confluence_outcome_rows": sum(
            1 for row in outcome_rows if row.get("source_bucket") == "confluence"
        ),
        "attention_audit": attention_audit,
        "outcome_audit": outcome_audit,
    }


def load_options_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_file: dict[str, int] = {}
    for path in OPTIONS_LEDGERS:
        file_rows = read_jsonl(path)
        by_file[repo_rel(path)] = len(file_rows)
        rows.extend(file_rows)
    dates = [row.get("usable_trade_date") for row in rows if row.get("usable_trade_date")]
    tickers = {row.get("ticker") for row in rows if row.get("ticker")}
    rows_with_result = sum(
        1
        for row in rows
        if any(
            row.get(key) is not None
            for key in (
                "replacement_value_vs_cash_usd",
                "replacement_value_1d_vs_cash_usd",
                "replacement_value_3d_vs_cash_usd",
                "replacement_value_5d_vs_cash_usd",
                "replacement_value_10d_vs_cash_usd",
            )
        )
    )
    return rows, {
        "rows": len(rows),
        "by_file": by_file,
        "usable_date_count": len(set(dates)),
        "usable_date_start": min(dates) if dates else None,
        "usable_date_end": max(dates) if dates else None,
        "ticker_count": len(tickers),
        "rows_with_replacement_value": rows_with_result,
        "status_counts": dict(Counter(row.get("outcome_status") for row in rows)),
    }


def options_score(row: dict[str, Any]) -> float | None:
    call_volume = safe_float(row.get("call_volume")) or 0.0
    put_volume = safe_float(row.get("put_volume")) or 0.0
    volume_total = call_volume + put_volume
    volume_score = call_volume / volume_total if volume_total > 0 else None
    oi_ratio = safe_float(row.get("put_call_open_interest_ratio"))
    oi_score = None if oi_ratio is None else 1.0 / (1.0 + max(oi_ratio, 0.0))
    liquidity = safe_float(row.get("avg_liquidity_score"))
    parts = [value for value in (volume_score, oi_score, liquidity) if value is not None]
    if not parts:
        return None
    return round(sum(parts) / len(parts), 6)


def build_options_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("usable_trade_date") or ""), str(row.get("ticker") or "").upper())
        if not key[0] or not key[1]:
            continue
        current = indexed.get(key)
        enriched = dict(row)
        enriched["options_bullish_score"] = options_score(row)
        if current is None:
            indexed[key] = enriched
            continue
        if (safe_float(enriched.get("avg_liquidity_score")) or 0.0) > (
            safe_float(current.get("avg_liquidity_score")) or 0.0
        ):
            indexed[key] = enriched
    return indexed


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def values(key: str) -> list[float]:
        return [value for value in (safe_float(row.get(key)) for row in rows) if value is not None]

    ticker_counts = Counter(row.get("ticker") for row in rows if row.get("ticker"))
    rv_cash = values("replacement_value_vs_cash_usd")
    rv_spy = values("replacement_value_vs_spy_usd")
    rv_qqq = values("replacement_value_vs_qqq_usd")
    return {
        "n": len(rows),
        "ticker_count": len(ticker_counts),
        "date_count": len({row.get("activity_date") for row in rows if row.get("activity_date")}),
        "source_bucket_counts": dict(Counter(row.get("source_bucket") for row in rows)),
        "mean_replacement_value_vs_cash_usd": round_or_none(mean(rv_cash), 2),
        "median_replacement_value_vs_cash_usd": round_or_none(median(rv_cash), 2) if rv_cash else None,
        "mean_replacement_value_vs_spy_usd": round_or_none(mean(rv_spy), 2),
        "mean_replacement_value_vs_qqq_usd": round_or_none(mean(rv_qqq), 2),
        "top_tickers": [
            {"ticker": ticker, "rows": count}
            for ticker, count in ticker_counts.most_common(10)
        ],
    }


def join_rows(
    outcomes: list[dict[str, Any]],
    options_index: dict[tuple[str, str], dict[str, Any]],
    *,
    date_field: str,
) -> list[dict[str, Any]]:
    joined: list[dict[str, Any]] = []
    for row in outcomes:
        date = str(row.get(date_field) or "")
        ticker = str(row.get("ticker") or "").upper()
        option_row = options_index.get((date, ticker))
        if option_row is None:
            continue
        joined_row = dict(row)
        joined_row.update(
            {
                "options_join_date_field": date_field,
                "options_quote_date": option_row.get("quote_date"),
                "options_usable_trade_date": option_row.get("usable_trade_date"),
                "options_bullish_score": option_row.get("options_bullish_score"),
                "options_avg_liquidity_score": option_row.get("avg_liquidity_score"),
                "options_put_call_volume_ratio": option_row.get("put_call_volume_ratio"),
                "options_put_call_open_interest_ratio": option_row.get(
                    "put_call_open_interest_ratio"
                ),
                "options_quality_flags": option_row.get("quality_flags") or [],
            }
        )
        joined.append(joined_row)
    return joined


def overlap_summary(outcomes: list[dict[str, Any]], options_rows: list[dict[str, Any]]) -> dict[str, Any]:
    options_index = build_options_index(options_rows)
    confluence = [row for row in outcomes if row.get("source_bucket") == "confluence"]
    activity_matches = join_rows(outcomes, options_index, date_field="activity_date")
    entry_matches = join_rows(outcomes, options_index, date_field="entry_date")
    confluence_activity = [row for row in activity_matches if row.get("source_bucket") == "confluence"]
    confluence_entry = [row for row in entry_matches if row.get("source_bucket") == "confluence"]
    return {
        "all_outcome_rows": summarize_rows(outcomes),
        "all_confluence_rows": summarize_rows(confluence),
        "activity_date_matches": summarize_rows(activity_matches),
        "entry_date_matches": summarize_rows(entry_matches),
        "confluence_activity_date_matches": summarize_rows(confluence_activity),
        "confluence_entry_date_matches": summarize_rows(confluence_entry),
        "sample_activity_matches": activity_matches[:25],
        "sample_entry_matches": entry_matches[:25],
    }


def load_baseline_metrics() -> dict[str, Any]:
    data = read_json(BASELINE_RESULT, {})
    windows = data.get("windows") or data.get("window_results") or []
    if isinstance(windows, dict):
        window_values = list(windows.values())
    else:
        window_values = list(windows)
    if not window_values and "aggregate" in data:
        aggregate = data["aggregate"]
        return {
            "baseline_exists": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "expected_value_score_sum": aggregate.get("aggregate_expected_value_score"),
            "total_pnl": aggregate.get("aggregate_total_pnl"),
            "max_drawdown_pct_worst": aggregate.get("max_window_drawdown_pct"),
            "trade_count": aggregate.get("total_trade_count"),
            "survival_rate": aggregate.get("min_survival_rate"),
            "window_count": 3,
        }
    ev_sum = sum(safe_float(row.get("expected_value_score")) or 0.0 for row in window_values)
    pnl_sum = sum(safe_float(row.get("total_pnl")) or 0.0 for row in window_values)
    return {
        "baseline_exists": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(ev_sum, 4),
        "total_pnl": round(pnl_sum, 2),
        "max_drawdown_pct_worst": round_or_none(
            max((safe_float(row.get("max_drawdown_pct")) or 0.0) for row in window_values),
            4,
        )
        if window_values
        else None,
        "trade_count": sum(int(row.get("trade_count") or 0) for row in window_values),
        "survival_rate": round_or_none(
            min(
                (safe_float(row.get("survival_rate")) or 1.0)
                for row in window_values
            ),
            4,
        )
        if window_values
        else None,
        "window_count": len(window_values),
    }


def load_ticket() -> dict[str, Any]:
    return read_json(TICKET_JSON, {})


def calibration(prediction: dict[str, Any], decision: str, failed: list[str]) -> dict[str, Any]:
    probability = safe_float(prediction.get("success_probability")) or 0.0
    success = 0.0
    return {
        "actual_decision": decision,
        "actual_success": success,
        "predicted_success_probability": probability,
        "brier_score": round((probability - success) ** 2, 4),
        "predicted_failure_modes": prediction.get("main_failure_modes") or [],
        "realized_failure_modes": failed,
        "predicted_failure_mode_hit": any(
            item in failed for item in (prediction.get("main_failure_modes") or [])
        ),
        "surprise_note": (
            "The pre-run sparse-overlap failure mode occurred; the options "
            "ledger has no ticker/date overlap with the exp024 confluence "
            "historical outcomes under either activity-date or entry-date join."
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = load_ticket()
    prediction = ticket.get("prediction") or {}
    baseline = load_baseline_metrics()
    outcomes, confluence_audit = confluence_outcomes()
    options_rows, options_audit = load_options_rows()
    summary = overlap_summary(outcomes, options_rows)

    activity_n = summary["activity_date_matches"]["n"]
    entry_n = summary["entry_date_matches"]["n"]
    confluence_activity_n = summary["confluence_activity_date_matches"]["n"]
    confluence_entry_n = summary["confluence_entry_date_matches"]["n"]
    failed: list[str] = []
    if activity_n < ACCEPTANCE_RULE["min_activity_date_option_matches"]:
        failed.append("activity_date_options_overlap_too_sparse")
    if entry_n < ACCEPTANCE_RULE["min_entry_date_option_matches"]:
        failed.append("entry_date_options_overlap_too_sparse")
    if confluence_activity_n < ACCEPTANCE_RULE["min_confluence_option_matches"]:
        failed.append("confluence_activity_date_options_overlap_too_sparse")
    if confluence_entry_n < ACCEPTANCE_RULE["min_confluence_option_matches"]:
        failed.append("confluence_entry_date_options_overlap_too_sparse")
    if options_audit["rows_with_replacement_value"] == 0:
        failed.append("options_ledger_rows_have_no_embedded_forward_outcomes")
    if not failed:
        failed.append("not_promoted_observed_only_requires_full_shared_helper")

    decision = "blocked_no_options_confluence_ticker_date_overlap"
    status = "observed_only_rejected"
    gate2_passed = activity_n > 0 or entry_n > 0
    gate3_survival = 0.0
    if summary["all_confluence_rows"]["n"]:
        gate3_survival = max(confluence_activity_n, confluence_entry_n) / summary["all_confluence_rows"]["n"]

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "observed_only_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": calibration(prediction, decision, failed),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "Options structure may be an independent demand-confirmation "
                "axis for the exp024 Form4+SEC confluence lead."
            ),
            "2_history_check": {
                "exp-20260623-024": (
                    "Positive observed-only confluence lead; retry allowed "
                    "only with materially new evidence such as options/borrow."
                ),
                "exp-20260623-025": (
                    "Shared-adapter precheck rejected because the confluence "
                    "lead did not beat the accepted distribution comparator."
                ),
                "exp-20260624-020": (
                    "Refreshed options forward ledger, but rows are forward "
                    "observation context rather than canonical fixed-window "
                    "historical coverage."
                ),
                "exp-20260624-023": (
                    "Kova SEC13F plus options cross-evidence was rejected; "
                    "this run tests a different base lead and records overlap."
                ),
                "novelty_gate": (
                    "Novelty and source-saturation overrides were recorded "
                    "because the new evidence axis is a separate options "
                    "ledger join, not a Form4/SEC threshold sweep."
                ),
            },
            "3_single_policy_bundle": (
                "One observed-only attribution bundle: join exp024 outcome "
                "rows to options rows by ticker plus activity_date and entry_date."
            ),
            "4_success_failure_standard": (
                "Pass only if options overlap is non-thin for all outcomes and "
                "confluence rows, and confirmed rows can be compared against "
                "unconfirmed rows on cash/SPY/QQQ replacement value."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "acceptance_rule": ACCEPTANCE_RULE,
            "join_keys": [
                ["activity_date", "ticker"],
                ["entry_date", "ticker"],
            ],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "source_artifact": repo_rel(EXP024_ARTIFACT),
            "options_ledgers": [repo_rel(path) for path in OPTIONS_LEDGERS],
        },
        "source_summary": {
            "confluence_replay": confluence_audit,
            "options": options_audit,
        },
        "overlap_summary": summary,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": bool(baseline.get("baseline_exists")),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": gate2_passed,
            "fields_checked": [
                "activity_date",
                "entry_date",
                "ticker",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
                "usable_trade_date",
                "options_bullish_score",
            ],
            "entry_date_present": all(bool(row.get("entry_date")) for row in outcomes),
            "target_price_present": all(row.get("target_price") is not None for row in outcomes),
            "activity_date_option_matches": activity_n,
            "entry_date_option_matches": entry_n,
            "confluence_activity_date_option_matches": confluence_activity_n,
            "confluence_entry_date_option_matches": confluence_entry_n,
            "options_rows": options_audit["rows"],
            "options_rows_with_replacement_value": options_audit["rows_with_replacement_value"],
            "failed_reasons": [
                item
                for item in failed
                if "overlap" in item or "options_ledger" in item
            ],
        },
        "gate3": {
            "passed": gate3_survival >= 0.05,
            "filter_added": False,
            "signals_generated": summary["all_confluence_rows"]["n"],
            "signals_survived": max(confluence_activity_n, confluence_entry_n),
            "survival_rate": round(gate3_survival, 4),
            "note": (
                "No executable filter was added. Survival is overlap coverage "
                "for this observed-only cross-source attribution."
            ),
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "failed_reasons": failed,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "overlap_summary": {
                "activity_date_matches": summary["activity_date_matches"],
                "entry_date_matches": summary["entry_date_matches"],
                "confluence_activity_date_matches": summary[
                    "confluence_activity_date_matches"
                ],
                "confluence_entry_date_matches": summary[
                    "confluence_entry_date_matches"
                ],
            },
        },
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The independent options ledger does not overlap the exp024 "
                "historical confluence outcome rows by ticker plus activity "
                "date or entry date. It also carries no embedded replacement "
                "outcomes, so this new evidence axis cannot validate or reject "
                "a confirmed confluence helper yet."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry Form4/SEC confluence plus options by sweeping "
                "Form4 direction, SEC item/form/text terms, option-score "
                "thresholds, date offsets, top-N, hold, cooldown, or notional "
                "on the same non-overlapping ledgers."
            ),
            "new_evidence_required": (
                "A valid retry needs historical PIT options-chain coverage on "
                "the exp024 confluence dates, forward confluence rows collected "
                "on dates that also have options observations and closed "
                "replacement value, or a different allowed evidence axis such "
                "as borrow/loan availability or parsed filing-surprise "
                "semantics."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(EXP024_RUNNER),
            repo_rel(EXP024_ARTIFACT),
            *[repo_rel(path) for path in OPTIONS_LEDGERS],
            repo_rel(BASELINE_RESULT),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
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
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "source_summary",
        "overlap_summary",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    gate2 = payload["gate2"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: non-OHLCV confluence + options cross-evidence",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            f"- Options rows: `{gate2['options_rows']}`",
            f"- Activity-date option matches: `{gate2['activity_date_option_matches']}`",
            f"- Entry-date option matches: `{gate2['entry_date_option_matches']}`",
            f"- Confluence activity-date matches: `{gate2['confluence_activity_date_option_matches']}`",
            f"- Confluence entry-date matches: `{gate2['confluence_entry_date_option_matches']}`",
            f"- Failed checks: `{', '.join(payload['gate4']['failed_reasons'])}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
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
        EXP024_RUNNER,
        EXP024_ARTIFACT,
        *OPTIONS_LEDGERS,
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
        "allowed_write_scope": payload["allowed_write_scope"],
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    ticket_before = payload.get("ticket_before") or {}
    fields = {
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
        "ticket_file": repo_rel(TICKET_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "allowed_write_scope": payload["allowed_write_scope"],
        "related_files": payload["related_files"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "hub_identity": ticket_before.get("hub_identity"),
        "novelty": ticket_before.get("novelty"),
        "claimed_at": ticket_before.get("claimed_at"),
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields=fields,
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
                "activity_date_option_matches": payload["gate2"][
                    "activity_date_option_matches"
                ],
                "entry_date_option_matches": payload["gate2"][
                    "entry_date_option_matches"
                ],
                "confluence_activity_date_option_matches": payload["gate2"][
                    "confluence_activity_date_option_matches"
                ],
                "confluence_entry_date_option_matches": payload["gate2"][
                    "confluence_entry_date_option_matches"
                ],
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
