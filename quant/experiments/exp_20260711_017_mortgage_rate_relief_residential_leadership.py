"""exp-20260711-017: mortgage-rate relief / residential leadership scout.

Private replay scout on a new official weekly FRED source. The only decision
hypothesis is that two consecutive MORTGAGE30US declines create demand relief
for liquid Residential Construction leaders. Entry is next session open and
exit is after ten sessions under the frozen stock-leadership replay policy.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260711_016_treasury_2s10s_steepening_financial_leadership as prior  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260711-017"
OWNER = "alpha-explore"
SLUG = "mortgage_rate_relief_residential_leadership"
RUNNER = f"quant/experiments/exp_20260711_017_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_017_{SLUG}.json"
MORTGAGE_ROWS_JSON = OUT_DIR / "fred_mortgage30us_weekly.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Private replay scout: two consecutive weekly declines in FRED "
    "MORTGAGE30US define mortgage-rate demand relief; liquid Residential "
    "Construction price leaders should improve next-open 10-session after-cost "
    "EV and PnL across the canonical windows."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_new_data_shape"
MECHANISM_FAMILY = "production_visible_mortgage_rate_residential_relation_candidate_pool"
TRIAL_FAMILY = "mortgage_rate_relief_residential_leadership_candidate_pool"
TRIAL_VARIANT_ID = "mortgage30us_two_week_decline_residential_top2_10d_v1"
CHANGED_VARIABLE = "mortgage30us_two_consecutive_weekly_declines_residential_construction_leadership_v1"
NEW_EVIDENCE_TYPE = "new_data_source_fred_mortgage_rate"
NEW_EVIDENCE_AXIS = (
    "New data source and issuer relation: official weekly FRED MORTGAGE30US "
    "history has not been used by prior Ginger experiments, and the response "
    "is restricted to Residential Construction rather than broad risk-on beta."
)
NEARBY_PRIORS = [
    "exp-20260711-004",
    "exp-20260711-013",
    "exp-20260711-016",
]
CAUSAL_COMPONENTS = [
    "FRED MORTGAGE30US weekly observations",
    "fixed two consecutive weekly declines",
    "Residential Construction-only frozen liquid stock selector",
    "next-open 10-session paper replay",
    "canonical costs and Gate 1-4",
    "accepted VIXY and MOVE comparators",
    "fingerprint coverage regression",
]
PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "housing_relation_relabels_rate_beta",
        "industry_sample_too_sparse",
        "window_regression",
        "accepted_relief_comparator_not_beaten",
        "concentration_failed",
        "fred_fetch_unavailable",
    ],
    "confidence_reason": (
        "Weekly mortgage-rate relief has a direct housing-demand transmission "
        "mechanism and the coverage-only preflight found 8/12/10 events across "
        "the three windows. Odds remain low because recent macro sources mostly "
        "relabeled beta and a narrow residential universe may be sparse."
    ),
    "recorded_at": "2026-07-11T12:06:33Z",
}
PRODUCTION_IMPACT = dict(prior.PRODUCTION_IMPACT)
PRODUCTION_IMPACT.update(
    {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "trade_enabled": False,
        "scope": "experiment_local_private_replay_scout",
    }
)
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/**",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]

MORTGAGE_TICKER = "MORTGAGE30US"
MORTGAGE_SERIES = "MORTGAGE30US"
FRED_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={MORTGAGE_SERIES}"
FETCH_START = "2024-08-01"
FETCH_END = "2026-04-22"
RESIDENTIAL_INDUSTRY = "Residential Construction"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fetch_mortgage_rows() -> list[dict[str, Any]]:
    if MORTGAGE_ROWS_JSON.exists():
        cached = json.loads(MORTGAGE_ROWS_JSON.read_text(encoding="utf-8"))
        if cached.get("rows"):
            return list(cached["rows"])
    with urllib.request.urlopen(FRED_URL, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    rows: list[dict[str, Any]] = []
    for source in csv.DictReader(io.StringIO(text)):
        day = str(source.get("observation_date") or "")[:10]
        value = number(source.get(MORTGAGE_SERIES))
        if not day or value is None or day < FETCH_START or day > FETCH_END:
            continue
        rows.append(
            {
                "Date": day,
                "Open": value,
                "High": value,
                "Low": value,
                "Close": value,
                "Volume": 0.0,
            }
        )
    if len(rows) < 85:
        raise RuntimeError(f"FRED MORTGAGE30US canonical coverage too small: {len(rows)} rows")
    prior.scaffold.prior.base.write_json(
        MORTGAGE_ROWS_JSON,
        {
            "source": "Freddie Mac Primary Mortgage Market Survey via FRED",
            "series_id": MORTGAGE_SERIES,
            "source_url": FRED_URL,
            "known_at": "weekly observation publication; paper entry is the next market session open",
            "fetched_at": utc_now(),
            "start": FETCH_START,
            "end": FETCH_END,
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def mortgage_relief_context(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(MORTGAGE_TICKER) or []
    idx = indices.get(MORTGAGE_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "after_weekly_publication_before_next_market_session_open",
    }
    if idx < 2:
        return {**context, "passed": False, "reason": "insufficient_mortgage_history"}
    current = number(rows[idx].get("Close"))
    previous = number(rows[idx - 1].get("Close"))
    prior_value = number(rows[idx - 2].get("Close"))
    if current is None or previous is None or prior_value is None:
        return {**context, "passed": False, "reason": "missing_mortgage_rate"}
    passed = current < previous < prior_value
    return {
        **context,
        "mortgage30us": round(current, 6),
        "mortgage30us_prior": round(previous, 6),
        "mortgage30us_two_weeks_prior": round(prior_value, 6),
        "two_week_change_pct_points": round(current - prior_value, 6),
        "passed": passed,
        "reason": "mortgage_rate_two_consecutive_weekly_declines" if passed else "not_two_consecutive_declines",
    }


def mortgage_candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    row = prior.scaffold.prior.base.BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None or str(row.get("industry") or "") != RESIDENTIAL_INDUSTRY:
        return None
    row["source"] = "FRED_MORTGAGE_RATE_RELIEF_RESIDENTIAL_LEADERSHIP_PAPER"
    row["mortgage_rate_relief_context"] = row.pop("macro_relief_context", kwargs["context"])
    row["rule_version"] = CHANGED_VARIABLE
    return row


def calibration(payload: dict[str, Any], lead: bool) -> dict[str, Any]:
    failed = list(payload["gate4"].get("failed_reasons") or [])
    probability = float(PREDICTION["success_probability"])
    hit: list[str] = []
    if any("sample" in reason or "window_coverage" in reason for reason in failed):
        hit.append("industry_sample_too_sparse")
    if any("window" in reason for reason in failed):
        hit.append("window_regression")
    if any("vixy" in reason or "comparator" in reason for reason in failed):
        hit.extend(["accepted_relief_comparator_not_beaten", "housing_relation_relabels_rate_beta"])
    if any("concentration" in reason for reason in failed):
        hit.append("concentration_failed")
    return {
        "predicted_success_probability": probability,
        "actual_success": lead,
        "brier_score": round((probability - (1.0 if lead else 0.0)) ** 2, 6),
        "predicted_failure_modes": list(PREDICTION["main_failure_modes"]),
        "predicted_failure_modes_hit": sorted(set(hit)),
        "failed_reasons": failed,
    }


def configure_prior() -> None:
    values = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "OWNER": OWNER,
        "SLUG": SLUG,
        "RUNNER": RUNNER,
        "RUNNER_PS": RUNNER_PS,
        "RUNNER_COMMAND": RUNNER_COMMAND,
        "OUT_DIR": OUT_DIR,
        "OUT_JSON": OUT_JSON,
        "CURVE_ROWS_JSON": MORTGAGE_ROWS_JSON,
        "LOG_JSON": LOG_JSON,
        "CARD_MD": CARD_MD,
        "MANIFEST_JSON": MANIFEST_JSON,
        "TICKET_JSON": TICKET_JSON,
        "REGISTRY_JSON": REGISTRY_JSON,
        "HYPOTHESIS": HYPOTHESIS,
        "CHANGE_TYPE": CHANGE_TYPE,
        "IMPLEMENTATION_MODE": IMPLEMENTATION_MODE,
        "MECHANISM_FAMILY": MECHANISM_FAMILY,
        "TRIAL_FAMILY": TRIAL_FAMILY,
        "TRIAL_VARIANT_ID": TRIAL_VARIANT_ID,
        "CHANGED_VARIABLE": CHANGED_VARIABLE,
        "NEW_EVIDENCE_TYPE": NEW_EVIDENCE_TYPE,
        "NEW_EVIDENCE_AXIS": NEW_EVIDENCE_AXIS,
        "NEARBY_PRIORS": NEARBY_PRIORS,
        "CAUSAL_COMPONENTS": CAUSAL_COMPONENTS,
        "PREDICTION": PREDICTION,
        "PRODUCTION_IMPACT": PRODUCTION_IMPACT,
        "ALLOWED_WRITE_SCOPE": ALLOWED_WRITE_SCOPE,
        "CURVE_TICKER": MORTGAGE_TICKER,
        "CURVE_SERIES": MORTGAGE_SERIES,
        "FRED_URL": FRED_URL,
        "FETCH_START": FETCH_START,
        "FETCH_END": FETCH_END,
        "FINANCIAL_SECTOR": RESIDENTIAL_INDUSTRY,
        "fetch_curve_rows": fetch_mortgage_rows,
        "curve_steepening_context": mortgage_relief_context,
        "curve_candidate_for_ticker": mortgage_candidate_for_ticker,
        "calibration": calibration,
    }
    for name, value in values.items():
        setattr(prior, name, value)


def build_payload() -> dict[str, Any]:
    configure_prior()
    payload = prior.build_payload()
    lead = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "decision": (
                "positive_replay_lead_not_promoted_mortgage_rate_residential_leadership"
                if lead
                else "observed_only_rejected_mortgage_rate_residential_leadership"
            ),
            "observed_only_lead": lead,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "fingerprint_caveat": (
                "Reservation overmatched the unseen FRED mortgage source into ohlcv_momentum; "
                "exp017 adds the dedicated fred_mortgage_rate key before closeout."
            ),
        }
    )
    events = payload["data_coverage"].pop("steepening_events_by_window", {})
    payload["data_coverage"].update(
        {
            "source": "Freddie Mac Primary Mortgage Market Survey via FRED",
            "series_id": MORTGAGE_SERIES,
            "mortgage_relief_events_by_window": events,
            "candidate_industry": RESIDENTIAL_INDUSTRY,
        }
    )
    for key in ("t10y2y_sma_sessions", "t10y2y_event", "candidate_sector"):
        payload["parameters"].pop(key, None)
    payload["parameters"].update(
        {
            "mortgage_event": "two_consecutive_weekly_declines",
            "candidate_industry": RESIDENTIAL_INDUSTRY,
            "stock_selector": "unchanged_exp_20260607_018_except_predeclared_industry_relation",
        }
    )
    payload["gate2"]["runtime_fields"] = [
        value.replace("FRED T10Y2Y daily Close with 20-session history", "FRED MORTGAGE30US weekly observation with two-row history")
        .replace("candidate sector == Financial Services", "candidate industry == Residential Construction")
        for value in payload["gate2"].get("runtime_fields", [])
    ]
    payload["gate3"]["note"] = (
        "No core filter or entry rule was added. The mortgage-rate relief "
        "source is additive default-off paper, so core survival is unchanged."
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    move_ev = 0.3344
    move_pnl = 7548.90
    move_passed = (
        float(aggregate["expected_value_score_delta_sum"]) > move_ev
        and float(aggregate["total_pnl_delta_sum"]) > move_pnl
    )
    payload["accepted_move_comparator"] = {
        "experiment_id": "exp-20260711-004",
        "artifact": "data/experiments/exp-20260711-004/exp_20260711_004_move_rate_volatility_relief_shared_paper.json",
        "aggregate_ev_delta": move_ev,
        "aggregate_pnl_delta": move_pnl,
        "candidate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "candidate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "passed": move_passed,
    }
    if not move_passed and "accepted_move_comparator_not_beaten" not in payload["gate4"]["failed_reasons"]:
        payload["gate4"]["failed_reasons"].append("accepted_move_comparator_not_beaten")
    payload["gate4"]["decision"] = "rejected_mortgage_rate_relief_residential_leadership"
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed mortgage-rate relief / Residential Construction relation cleared the private scout bar across all canonical windows."
            if lead
            else "The fixed mortgage-rate relief / Residential Construction relation did not add robust after-cost value; it was sparse, concentrated, window-fragile, or another rate-beta timing label."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry MORTGAGE30US decline streaks, moving averages, levels, persistence, housing subindustries, ticker lists, stock filters, top-N, hold, cooldown, notional, windows, or response curves on these rows."
        ),
        "new_evidence_required": (
            "A retry requires materially settled prospective rows from a fixed shared helper if this is a lead, or a genuinely different publication-timed housing demand/permit/mortgage-application source if rejected."
        ),
    }
    payload["calibration"] = calibration(payload, lead)
    payload["rejection_reason"] = None if lead else ";".join(
        payload["gate4"].get("failed_reasons") or ["gate4_not_passed"]
    )
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["related_files"] = [
        RUNNER,
        "quant/experiments/exp_20260607_018_volatility_relief_stock_leadership.py",
        prior.scaffold.prior.base.repo_rel(MORTGAGE_ROWS_JSON),
        "scripts/experiment_fingerprint.py",
        "quant/test_experiment_fingerprint.py",
    ]
    payload["changed_files"] = ALLOWED_WRITE_SCOPE
    payload["reproduction_commands"] = [
        f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
        RUNNER_COMMAND,
        ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
        ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
    ]
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": "candidate_pool: weekly mortgage-rate relief may favor Residential Construction leaders",
        "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS, "novelty_override": False},
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": "Canonical Gate 1-4 plus accepted VIXY/MOVE comparators; positive remains an observed-only lead.",
        "5_reproducibility": RUNNER_COMMAND,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Mortgage-Rate Residential Leadership",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Result",
            "",
            f"- MORTGAGE30US coverage: `{payload['data_coverage']['rows_by_window']}`",
            f"- Relief events: `{payload['data_coverage']['mortgage_relief_events_by_window']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Accepted VIXY comparator passed: `{payload['closest_accepted_comparator']['passed']}`",
            f"- Accepted MOVE comparator passed: `{payload['accepted_move_comparator']['passed']}`",
            f"- Failed gates: `{payload['gate4'].get('failed_reasons') or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    )


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Bind inherited compact-log output to this wrapper's experiment identity.

    The replay implementation is intentionally inherited from exp-20260711-002,
    but its compact-log builder closes over the base module's identity constants.
    Rebinding every identity-bearing field prevents this wrapper from writing to
    the MOVE experiment's shard.
    """
    base = prior.scaffold.prior.base
    row = base.compact_log(payload)
    row.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": HYPOTHESIS,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "prediction": PREDICTION,
            "artifact": base.repo_rel(OUT_JSON),
            "log": base.repo_rel(LOG_JSON),
            "changed_files": ALLOWED_WRITE_SCOPE,
        }
    )
    return row


def persist(payload: dict[str, Any]) -> None:
    base = prior.scaffold.prior.base
    base.write_json(OUT_JSON, payload)
    save_experiment_log_entry(
        build_log_record(payload),
        allow_duplicate=True,
        expected_experiment_id=EXPERIMENT_ID,
    )
    base.write_text(CARD_MD, build_card(payload))
    aggregate = payload["delta_metrics"]["aggregate"]
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": base.repo_rel(OUT_JSON),
            "log": base.repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "baseline_result_file": "data/experiments/exp-20260602-003/exp_20260602_003_post_earnings_explicit_continuation.json",
            "decision": payload["decision"],
            "artifact": base.repo_rel(OUT_JSON),
            "log": base.repo_rel(LOG_JSON),
            "card_file": base.repo_rel(CARD_MD),
            "revision_manifest_file": base.repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
            "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
            "changed_files": ALLOWED_WRITE_SCOPE,
            "fingerprint_caveat": payload["fingerprint_caveat"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": True,
        },
    )
    prior.write_manifest(payload)


def main() -> int:
    configure_prior()
    prior.build_card = build_card
    payload = build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "mortgage_rows": payload["data_coverage"]["row_count"],
                "mortgage_relief_events": payload["data_coverage"]["mortgage_relief_events_by_window"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "vixy_comparator_passed": payload["closest_accepted_comparator"]["passed"],
                "move_comparator_passed": payload["accepted_move_comparator"]["passed"],
                "failed_reasons": payload["gate4"].get("failed_reasons"),
                "artifact": prior.scaffold.prior.base.repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
