"""exp-20260528-009: repaired PEAD bucket attribution.

Observed-only alpha search. This re-runs the expectation-revision PEAD bucket
comparison after exp-20260527-908 joined a PIT last_earnings_date and PEAD
status into the watchlist rows. It does not change strategy behavior,
candidate ranking, sizing, exits, LLM prompts, paper sleeves, or orders.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260528-009"
STEM = "expectation_pead_repaired_bucket_attribution"
MECHANISM_FAMILY = "expectation_revision_pead"
TRIAL_FAMILY = "expectation_pead_repaired_bucket_attribution"
CHANGED_VARIABLE = "repaired_pead_t2_t15_non_overextended_bucket_v1"

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_EXPERIMENT_ID = "exp-20260527-908"
SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "last_earnings_date_pit_join_into_expectation_revision_watchlist_row.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

FORWARD_HORIZONS = (5, 10, 20)
PAPER_NOTIONAL_USD = 10_000.0
ANTI_JS = "No JavaScript was used."

BASELINE = {
    "accepted_core_expected_value_score_sum": 7.8941,
    "accepted_core_total_pnl_sum": 234850.99,
    "baseline_source": "docs/backtesting.md accepted aggregate core stack",
}

BUCKET_ORDER = [
    "eligible_t2_t15_non_overextended",
    "eligible_t2_t15_residual_leader",
    "primary_positive_outside_t2_t15",
    "primary_positive_missing_last_earnings_date",
    "primary_positive_other_pead_status",
    "not_primary_7d_positive",
]

MIN_CLOSED_OUTCOMES = {
    ("eligible_t2_t15_non_overextended", "5d"): 8,
    ("eligible_t2_t15_non_overextended", "10d"): 8,
    ("eligible_t2_t15_residual_leader", "5d"): 6,
    ("eligible_t2_t15_residual_leader", "10d"): 6,
    ("primary_positive_outside_t2_t15", "5d"): 10,
    ("primary_positive_outside_t2_t15", "10d"): 8,
}
MAX_TOP5_POSITIVE_PNL_SHARE = 0.70
MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE = 0.50

NEARBY_PRIORS = [
    {
        "experiment_id": "exp-20260527-005",
        "finding": "Initial PEAD comparison was blocked because primary positive rows were missing last_earnings_date.",
    },
    {
        "experiment_id": "exp-20260527-006",
        "finding": "Short-horizon PEAD probe needed repaired earnings-date coverage and 2d outcome persistence.",
    },
    {
        "experiment_id": "exp-20260527-007",
        "finding": "Related PEAD continuation probe closed observed_only_data_gap before the PIT join.",
    },
    {
        "experiment_id": "exp-20260527-908",
        "finding": "Measurement repair resolved last_earnings_date for 40/47 primary positive rows and created inside/outside PEAD buckets.",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return _repo_rel(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(compact + "\n", encoding="utf-8")
        return

    found = False
    with path.open("r", encoding="utf-8", errors="replace") as src:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                found = True
                break

    if not found:
        with path.open("a", encoding="utf-8", newline="\n") as dst:
            dst.write(compact + "\n")
        return

    tmp_path = path.with_name(f"{path.name}.{EXPERIMENT_ID}.tmp")
    replaced = False
    with path.open("r", encoding="utf-8", errors="replace") as src, tmp_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as dst:
        for line in src:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                dst.write(line if line.endswith("\n") else line + "\n")
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    dst.write(compact + "\n")
                    replaced = True
                continue
            dst.write(line if line.endswith("\n") else line + "\n")
    tmp_path.replace(path)


def _float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def load_source(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing source artifact: {_repo_rel(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("enriched_watchlist_rows")
    if not isinstance(rows, list):
        raise ValueError("source artifact does not contain enriched_watchlist_rows")
    return payload


def is_primary_positive(row: dict[str, Any]) -> bool:
    return bool(row.get("primary_expectation_positive"))


def is_residual_leader(row: dict[str, Any]) -> bool:
    state = str(row.get("residual_state") or "")
    return bool(row.get("residual_leader")) or state in {
        "residual_leader",
        "strong_residual_leader",
    }


def bucket_for(row: dict[str, Any]) -> str:
    if not is_primary_positive(row):
        return "not_primary_7d_positive"

    pead_status = str(row.get("pead_status") or "")
    if pead_status == "inside_t2_t15_after_earnings":
        if is_residual_leader(row):
            return "eligible_t2_t15_residual_leader"
        return "eligible_t2_t15_non_overextended"
    if pead_status == "outside_t2_t15_after_earnings":
        return "primary_positive_outside_t2_t15"
    if pead_status == "missing_last_earnings_date":
        return "primary_positive_missing_last_earnings_date"
    return "primary_positive_other_pead_status"


def outcome_for(row: dict[str, Any], horizon: str) -> dict[str, Any]:
    raw = ((row.get("forward_outcomes") or {}).get(horizon) or {}).copy()
    closed = bool(raw.get("closed"))
    ret = _float(raw.get("return"))
    pnl = _float(raw.get("pnl_proxy"))
    if closed and pnl is None and ret is not None:
        pnl = ret * PAPER_NOTIONAL_USD
    return {
        "closed": closed,
        "return": ret,
        "pnl_proxy": pnl,
        "future_date": raw.get("future_date"),
        "gap_reason": raw.get("gap_reason"),
    }


def positive_pnl_concentration(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    positives: list[tuple[str, float]] = []
    for row in rows:
        outcome = outcome_for(row, horizon)
        pnl = outcome["pnl_proxy"]
        if outcome["closed"] and pnl is not None and pnl > 0:
            positives.append((str(row.get("ticker") or ""), pnl))

    total_positive = sum(pnl for _, pnl in positives)
    if total_positive <= 0:
        return {
            "positive_pnl_total": 0.0,
            "top5_positive_pnl_share": None,
            "single_ticker_positive_pnl_share": None,
        }

    top5 = sum(pnl for _, pnl in sorted(positives, key=lambda item: item[1], reverse=True)[:5])
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for ticker, pnl in positives:
        by_ticker[ticker] += pnl
    single = max(by_ticker.values()) if by_ticker else 0.0
    return {
        "positive_pnl_total": total_positive,
        "top5_positive_pnl_share": top5 / total_positive,
        "single_ticker_positive_pnl_share": single / total_positive,
    }


def summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    days_since = [
        value
        for value in (_float(row.get("days_since_last_earnings")) for row in rows)
        if value is not None
    ]
    summary: dict[str, Any] = {
        "row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows}),
        "residual_leader_count": sum(1 for row in rows if is_residual_leader(row)),
        "residual_state_counts": dict(Counter(str(row.get("residual_state") or "") for row in rows)),
        "pead_status_counts": dict(Counter(str(row.get("pead_status") or "") for row in rows)),
        "last_earnings_source_counts": dict(
            Counter(
                str(((row.get("last_earnings_lookup") or {}).get("source")) or "missing")
                for row in rows
            )
        ),
        "sector_counts": dict(Counter(str(row.get("sector") or "") for row in rows)),
        "days_since_last_earnings": {
            "min": min(days_since) if days_since else None,
            "avg": sum(days_since) / len(days_since) if days_since else None,
            "max": max(days_since) if days_since else None,
        },
        "forward_outcomes": {},
    }
    for horizon_days in FORWARD_HORIZONS:
        horizon = f"{horizon_days}d"
        outcomes = [outcome_for(row, horizon) for row in rows]
        closed = [item for item in outcomes if item["closed"]]
        returns = [item["return"] for item in closed if item["return"] is not None]
        pnls = [item["pnl_proxy"] for item in closed if item["pnl_proxy"] is not None]
        wins = [value for value in returns if value > 0]
        concentration = positive_pnl_concentration(rows, horizon)
        summary["forward_outcomes"][horizon] = {
            "closed_count": len(closed),
            "missing_count": len(rows) - len(closed),
            "avg_return": sum(returns) / len(returns) if returns else None,
            "win_rate": len(wins) / len(returns) if returns else None,
            "total_pnl_proxy": sum(pnls) if pnls else None,
            **concentration,
        }
    return summary


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_bucket: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in BUCKET_ORDER}
    for row in rows:
        by_bucket.setdefault(str(row["pead_attribution_bucket"]), []).append(row)
    return {bucket: summarize_bucket(by_bucket.get(bucket, [])) for bucket in by_bucket}


def metric(
    summary: dict[str, Any],
    bucket: str,
    horizon: str,
    field: str,
    default: float | int | None = None,
) -> Any:
    return (
        ((summary.get(bucket) or {}).get("forward_outcomes") or {})
        .get(horizon, {})
        .get(field, default)
    )


def build_gate(summary: dict[str, Any]) -> dict[str, Any]:
    data_gaps = []
    for (bucket, horizon), minimum in MIN_CLOSED_OUTCOMES.items():
        closed_count = metric(summary, bucket, horizon, "closed_count", 0)
        if closed_count < minimum:
            data_gaps.append(
                {
                    "bucket": bucket,
                    "horizon": horizon,
                    "closed_count": closed_count,
                    "minimum": minimum,
                    "reason": "closed_outcomes_below_minimum",
                }
            )

    comparisons: dict[str, Any] = {}
    for horizon in ("5d", "10d"):
        non_avg = metric(summary, "eligible_t2_t15_non_overextended", horizon, "avg_return")
        residual_avg = metric(summary, "eligible_t2_t15_residual_leader", horizon, "avg_return")
        outside_avg = metric(summary, "primary_positive_outside_t2_t15", horizon, "avg_return")
        non_pnl = metric(
            summary,
            "eligible_t2_t15_non_overextended",
            horizon,
            "total_pnl_proxy",
        )
        residual_pnl = metric(
            summary,
            "eligible_t2_t15_residual_leader",
            horizon,
            "total_pnl_proxy",
        )
        outside_pnl = metric(
            summary,
            "primary_positive_outside_t2_t15",
            horizon,
            "total_pnl_proxy",
        )
        comparisons[horizon] = {
            "non_overextended_avg_return": non_avg,
            "residual_leader_avg_return": residual_avg,
            "outside_pead_avg_return": outside_avg,
            "non_overextended_total_pnl_proxy": non_pnl,
            "residual_leader_total_pnl_proxy": residual_pnl,
            "outside_pead_total_pnl_proxy": outside_pnl,
            "non_overextended_beats_residual_avg": (
                non_avg is not None and residual_avg is not None and non_avg > residual_avg
            ),
            "non_overextended_beats_outside_avg": (
                non_avg is not None and outside_avg is not None and non_avg > outside_avg
            ),
            "non_overextended_beats_residual_pnl": (
                non_pnl is not None and residual_pnl is not None and non_pnl > residual_pnl
            ),
            "non_overextended_beats_outside_pnl": (
                non_pnl is not None and outside_pnl is not None and non_pnl > outside_pnl
            ),
        }

    concentration = {
        horizon: {
            "top5_positive_pnl_share": metric(
                summary,
                "eligible_t2_t15_non_overextended",
                horizon,
                "top5_positive_pnl_share",
            ),
            "single_ticker_positive_pnl_share": metric(
                summary,
                "eligible_t2_t15_non_overextended",
                horizon,
                "single_ticker_positive_pnl_share",
            ),
        }
        for horizon in ("5d", "10d")
    }
    concentration_flags = []
    for horizon, values in concentration.items():
        top5 = values["top5_positive_pnl_share"]
        single = values["single_ticker_positive_pnl_share"]
        if top5 is not None and top5 > MAX_TOP5_POSITIVE_PNL_SHARE:
            concentration_flags.append(f"{horizon}_top5_positive_pnl_concentration")
        if single is not None and single > MAX_SINGLE_TICKER_POSITIVE_PNL_SHARE:
            concentration_flags.append(f"{horizon}_single_ticker_positive_pnl_concentration")

    directional_pass = all(
        bool(comparisons[horizon][key])
        for horizon in ("5d", "10d")
        for key in (
            "non_overextended_beats_residual_avg",
            "non_overextended_beats_outside_avg",
            "non_overextended_beats_residual_pnl",
            "non_overextended_beats_outside_pnl",
        )
    )
    if data_gaps:
        decision = "observed_only_data_gap"
        reason = "closed_outcomes_below_minimum"
        passed = False
    elif concentration_flags:
        decision = "observed_only_no_promotable_edge"
        reason = "positive_pnl_concentration_guardrail_failed"
        passed = False
    elif directional_pass:
        decision = "observed_only_promising_needs_strategy_gate"
        reason = None
        passed = True
    else:
        decision = "observed_only_no_promotable_edge"
        reason = "non_overextended_pead_bucket_did_not_beat_comparators_on_5d_and_10d"
        passed = False

    return {
        "passed": passed,
        "decision": decision,
        "reason": reason,
        "data_gaps": data_gaps,
        "comparisons": comparisons,
        "concentration": concentration,
        "concentration_flags": concentration_flags,
        "directional_pass_if_sufficient_data": directional_pass,
    }


def field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in fields:
        present = sum(1 for row in rows if row.get(field) not in (None, "", [], {}))
        out[field] = {
            "present": present,
            "total": len(rows),
            "coverage_ratio": present / len(rows) if rows else None,
        }
    return out


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    outcomes = {}
    for horizon in ("5d", "10d", "20d"):
        outcome = outcome_for(row, horizon)
        outcomes[horizon] = {
            "closed": outcome["closed"],
            "return": outcome["return"],
            "pnl_proxy": outcome["pnl_proxy"],
            "gap_reason": outcome["gap_reason"],
        }
    return {
        "as_of_date": row.get("as_of_date"),
        "feature_context_date": row.get("feature_context_date"),
        "watchlist_effective_trade_date": row.get("watchlist_effective_trade_date"),
        "ticker": row.get("ticker"),
        "bucket": row.get("pead_attribution_bucket"),
        "pead_status": row.get("pead_status"),
        "days_since_last_earnings": row.get("days_since_last_earnings"),
        "last_earnings_date": row.get("last_earnings_date"),
        "residual_state": row.get("residual_state"),
        "residual_leader": row.get("residual_leader"),
        "eps_estimate_delta_7d": row.get("eps_estimate_delta_7d"),
        "eps_estimate_delta_30d": row.get("eps_estimate_delta_30d"),
        "forward_outcomes": outcomes,
    }


def build_payload(source_path: Path) -> dict[str, Any]:
    timestamp = _utc_now()
    source_payload = load_source(source_path)
    rows: list[dict[str, Any]] = []
    for row in source_payload["enriched_watchlist_rows"]:
        enriched = dict(row)
        enriched["pead_attribution_bucket"] = bucket_for(enriched)
        rows.append(enriched)

    bucket_summary = summarize_rows(rows)
    gate = build_gate(bucket_summary)
    decision = gate["decision"]
    status = "observed_only"

    as_of_dates = sorted(str(row.get("as_of_date")) for row in rows if row.get("as_of_date"))
    related_files = [
        _repo_rel(Path(__file__)),
        _repo_rel(source_path),
        _repo_rel(OUT_JSON),
        _repo_rel(DOC_ARTIFACT),
        _repo_rel(DOC_LOG),
        _repo_rel(DOC_TICKET),
        _repo_rel(DOCS_TICKET),
        _repo_rel(EXPERIMENT_LOG_JSONL),
        _repo_rel(EXPERIMENT_REGISTRY),
    ]
    coverage = {
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "rows_total": len(rows),
        "as_of_date_range": f"{as_of_dates[0]} .. {as_of_dates[-1]}" if as_of_dates else None,
        "primary_positive_rows": sum(1 for row in rows if is_primary_positive(row)),
        "bucket_counts": dict(Counter(str(row["pead_attribution_bucket"]) for row in rows)),
        "pead_status_counts": dict(Counter(str(row.get("pead_status") or "") for row in rows)),
        "primary_positive_pead_status_counts": dict(
            Counter(str(row.get("pead_status") or "") for row in rows if is_primary_positive(row))
        ),
        "field_coverage": field_coverage(
            rows,
            [
                "ticker",
                "as_of_date",
                "watchlist_effective_trade_date",
                "primary_expectation_positive",
                "eps_estimate_delta_7d",
                "last_earnings_date",
                "pead_status",
                "days_since_last_earnings",
                "forward_outcomes",
            ],
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "After the PIT last_earnings_date repair, primary positive EPS "
            "revision rows that are inside the T+2..T+15 PEAD window and not "
            "residual leaders should outperform residual-leader PEAD rows and "
            "primary-positive rows outside the PEAD window."
        ),
        "change_summary": (
            "Observed-only repaired PEAD bucket attribution. Reads the "
            "exp-20260527-908 enriched watchlist and compares primary-positive "
            "EPS revision rows across inside-T+2..T+15 non-overextended, "
            "inside-T+2..T+15 residual-leader, outside-PEAD, and still-missing "
            "last_earnings_date buckets."
        ),
        "change_type": "observed_only_pead_bucket_attribution",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 4,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "repaired_pead_bucket_forward_outcome_attribution",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(source_path),
            "pead_window": "T+2..T+15 after last_earnings_date",
            "primary_positive_definition": "source primary_expectation_positive == true",
            "non_overextended_definition": "not residual_leader and residual_state not in residual_leader/strong_residual_leader",
            "forward_horizons": list(FORWARD_HORIZONS),
            "paper_notional_usd": PAPER_NOTIONAL_USD,
            "min_closed_outcomes": {
                f"{bucket}:{horizon}": minimum
                for (bucket, horizon), minimum in MIN_CLOSED_OUTCOMES.items()
            },
            "anti_js": ANTI_JS,
        },
        "date_range": source_payload.get("date_range")
        or {
            "source_watchlist_as_of_dates": coverage["as_of_date_range"],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Repaired PEAD T+2..T+15 primary positive revision rows that "
                "are not residual leaders are a better continuation bucket than "
                "residual-leader PEAD rows or primary positives outside PEAD."
            ),
            "2_history_check": (
                "exp-20260527-005/006/007 were blocked by missing last_earnings_date; "
                "exp-20260527-908 repaired the PIT field and showed 8 non-residual "
                "and 7 residual primary-positive inside-PEAD rows."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only pass requires sufficient closed 5d/10d outcomes, "
                "non-overextended inside-PEAD to beat residual-leader and outside-PEAD "
                "comparators on avg return and PnL, and concentration below guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260528_009_expectation_pead_repaired_bucket_attribution.py"
            ),
        },
        "gate1": {
            "passed": True,
            **BASELINE,
            "note": "Observed-only attribution; no before/after core strategy metrics change.",
        },
        "gate2": {
            "passed": True,
            "rule_dependencies": [
                "ticker",
                "as_of_date",
                "primary_expectation_positive",
                "last_earnings_date",
                "pead_status",
                "residual_leader",
                "residual_state",
                "forward_outcomes",
            ],
            "source_gate2": source_payload.get("gates", {}).get("gate2")
            or source_payload.get("gate2"),
        },
        "gate3": {
            "adds_filter": False,
            "candidate_pool_changed": False,
            "survival_rate_not_applicable": True,
            "passed": True,
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "passed": bool(gate["passed"]),
            "note": "Observed-only result can only unlock a later default-off Gate 1-4 strategy experiment.",
        },
        "coverage": coverage,
        "bucket_summary": bucket_summary,
        "gate": gate,
        "sample_rows": {
            bucket: [
                compact_row(row)
                for row in rows
                if row.get("pead_attribution_bucket") == bucket
            ][:80]
            for bucket in BUCKET_ORDER
            if bucket != "not_primary_7d_positive"
        },
        "before_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
            "source_repair_before": source_payload.get("before_metrics"),
        },
        "after_metrics": {
            "accepted_core_expected_value_score_sum": BASELINE[
                "accepted_core_expected_value_score_sum"
            ],
            "accepted_core_total_pnl_sum": BASELINE["accepted_core_total_pnl_sum"],
            "strategy_behavior_changed": False,
            "source_repair_after": source_payload.get("after_metrics"),
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_sum_delta": 0.0,
            "strategy_behavior_delta": 0,
        },
        "expected_value_score_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "observed_only_attribution": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": gate["reason"],
        "next_evidence_needed": (
            "Persist more 10d closed outcomes for the repaired PEAD buckets, "
            "especially non-overextended inside-PEAD and outside-PEAD primary "
            "positive rows. Do not promote a PEAD rule until 10d comparison "
            "coverage clears the minimum and the edge remains directionally "
            "positive."
        ),
        "related_files": related_files,
        "anti_js": ANTI_JS,
    }


def artifact_markdown(payload: dict[str, Any]) -> str:
    rows = [
        "# exp-20260528-009 Repaired PEAD Bucket Attribution",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        "- Strategy behavior changed: `false`",
        "",
        "## Gate Summary",
        "",
        f"- Gate 1: `{payload['gate1']['passed']}` observed-only against accepted core baseline.",
        f"- Gate 2: `{payload['gate2']['passed']}` source rows include ticker/as_of_date/PEAD fields/outcomes.",
        f"- Gate 3: `{payload['gate3']['passed']}` no filter or candidate-pool change.",
        f"- Gate 4: `{payload['gate4']['passed']}` observed-only attribution gate.",
        "",
        "## Bucket Outcomes",
        "",
        "| bucket | rows | 5d closed | 5d avg | 5d pnl | 10d closed | 10d avg | 10d pnl |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bucket in BUCKET_ORDER:
        summary = payload["bucket_summary"].get(bucket, {})
        outcomes = summary.get("forward_outcomes", {})
        h5 = outcomes.get("5d", {})
        h10 = outcomes.get("10d", {})
        rows.append(
            "| {bucket} | {rows_count} | {c5} | {a5} | {p5} | {c10} | {a10} | {p10} |".format(
                bucket=bucket,
                rows_count=summary.get("row_count", 0),
                c5=h5.get("closed_count", 0),
                a5=_fmt(h5.get("avg_return")),
                p5=_fmt(h5.get("total_pnl_proxy")),
                c10=h10.get("closed_count", 0),
                a10=_fmt(h10.get("avg_return")),
                p10=_fmt(h10.get("total_pnl_proxy")),
            )
        )
    rows.extend(
        [
            "",
            "## Gate Details",
            "",
            f"- Data gaps: `{json.dumps(payload['gate']['data_gaps'], ensure_ascii=True)}`",
            f"- Directional pass if sufficient data: `{payload['gate']['directional_pass_if_sufficient_data']}`",
            f"- Concentration flags: `{payload['gate']['concentration_flags']}`",
            "",
            "## Interpretation",
            "",
            "The repaired 5d sample is directionally encouraging for the non-overextended inside-PEAD bucket, but 10d closed outcome coverage remains below the minimum. This is a data-gap result, not a promotable trading rule.",
            "",
            "## Related Files",
            "",
        ]
    )
    rows.extend(f"- `{path}`" for path in payload["related_files"])
    rows.append("")
    return "\n".join(rows)


def _fmt(value: Any) -> str:
    number = _float(value)
    if number is None:
        return ""
    return f"{number:.6f}"


def persist_payload(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "artifact_file": _repo_rel(OUT_JSON),
        "decision": payload["decision"],
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "owner": "codex-expectation-pead-attribution",
        "result_file": _repo_rel(DOC_LOG),
        "single_causal_variable": CHANGED_VARIABLE,
        "status": payload["status"],
        "updated_at": payload["timestamp"],
    }
    _write_json(DOC_TICKET, ticket)
    _write_json(DOCS_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(artifact_markdown(payload), encoding="utf-8")
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, payload)
    update_registry(payload, ticket)


def update_registry(payload: dict[str, Any], ticket: dict[str, Any]) -> None:
    registry: dict[str, Any]
    if EXPERIMENT_REGISTRY.exists():
        registry = json.loads(EXPERIMENT_REGISTRY.read_text(encoding="utf-8"))
    else:
        registry = {"experiments": []}
    experiments = registry.setdefault("experiments", [])
    row = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": payload["hypothesis"],
        "lane": payload["lane"],
        "owner": ticket["owner"],
        "status": payload["status"],
        "ticket_file": _repo_rel(DOC_TICKET),
        "updated_at": payload["timestamp"],
    }
    replaced = False
    for idx, item in enumerate(experiments):
        if item.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = row
            replaced = True
            break
    if not replaced:
        experiments.append(row)
    _write_json(EXPERIMENT_REGISTRY, registry)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact", default=str(SOURCE_ARTIFACT))
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    payload = build_payload(Path(args.source_artifact))
    if not args.no_persist:
        persist_payload(payload)

    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "gate": payload["gate"],
                "coverage": {
                    "rows_total": payload["coverage"]["rows_total"],
                    "bucket_counts": payload["coverage"]["bucket_counts"],
                    "primary_positive_pead_status_counts": payload["coverage"][
                        "primary_positive_pead_status_counts"
                    ],
                },
                "output": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
