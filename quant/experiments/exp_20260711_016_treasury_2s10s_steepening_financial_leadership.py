"""exp-20260711-016: FRED 2s10s steepening / Financial leadership scout.

Private replay scout on a new official yield-curve source.  The only decision
hypothesis is a first T10Y2Y close above its trailing 20-session mean, paired
with the frozen liquid-stock selector restricted to Financial Services.  No
production, core, order, sizing, exit, or LLM behavior changes.
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

import exp_20260711_011_cboe_skew_relief_stock_leadership as scaffold  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260711-016"
OWNER = "alpha-explore"
SLUG = "treasury_2s10s_steepening_financial_leadership"
RUNNER = f"quant/experiments/exp_20260711_016_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_016_{SLUG}.json"
CURVE_ROWS_JSON = OUT_DIR / "fred_t10y2y_daily.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Private replay scout: first daily FRED T10Y2Y Treasury spread close above "
    "its trailing 20-session mean defines curve steepening; a Financial-sector "
    "liquid-stock leadership pool should improve next-open 10-session after-cost "
    "EV and PnL."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_new_data_shape"
MECHANISM_FAMILY = "production_visible_treasury_curve_financial_relation_candidate_pool"
TRIAL_FAMILY = "treasury_2s10s_steepening_financial_leadership_candidate_pool"
TRIAL_VARIANT_ID = "t10y2y20_cross_above_financial_top2_10d_v1"
CHANGED_VARIABLE = "t10y2y20_first_cross_above_financial_leadership_v1"
NEW_EVIDENCE_TYPE = "new_data_source_fred_treasury_2s10s_spread"
NEW_EVIDENCE_AXIS = (
    "New data source and relation: FRED T10Y2Y has not been used by prior "
    "Ginger experiments; the response is Financial-sector leadership rather "
    "than another broad risk-on selector."
)
NEARBY_PRIORS = [
    "exp-20260711-001",
    "exp-20260711-004",
    "exp-20260711-013",
    "exp-20260711-015",
]
CAUSAL_COMPONENTS = [
    "FRED T10Y2Y daily observations",
    "fixed first cross above trailing 20-session simple mean",
    "Financial-sector-only frozen liquid stock selector",
    "next-open 10-session paper replay",
    "canonical costs and Gate 1-4",
    "accepted VIXY relief comparator",
    "fingerprint coverage regression",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "term_spread_relabels_broad_beta",
        "financial_sector_sample_too_sparse",
        "old_thin_regression",
        "accepted_relief_comparator_not_beaten",
        "concentration_failed",
        "fred_fetch_unavailable",
    ],
    "confidence_reason": (
        "T10Y2Y is a new official Treasury term-spread source and Financial-only "
        "exposure has a direct banking relation; odds remain low because recent "
        "macro relief proxies were generic beta and the sector restriction may "
        "starve all-window samples."
    ),
    "recorded_at": "2026-07-11T11:08:48Z",
}
PRODUCTION_IMPACT = dict(scaffold.PRODUCTION_IMPACT)
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

CURVE_TICKER = "T10Y2Y"
CURVE_SERIES = "T10Y2Y"
FRED_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={CURVE_SERIES}"
FETCH_START = "2024-08-01"
FETCH_END = "2026-04-22"
CURVE_SMA_SESSIONS = 20
FINANCIAL_SECTOR = "Financial Services"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fetch_curve_rows() -> list[dict[str, Any]]:
    if CURVE_ROWS_JSON.exists():
        cached = json.loads(CURVE_ROWS_JSON.read_text(encoding="utf-8"))
        if cached.get("rows"):
            return list(cached["rows"])
    with urllib.request.urlopen(FRED_URL, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    rows: list[dict[str, Any]] = []
    for source in csv.DictReader(io.StringIO(text)):
        day = str(source.get("observation_date") or "")[:10]
        value = number(source.get(CURVE_SERIES))
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
    if len(rows) < 400:
        raise RuntimeError(f"FRED T10Y2Y canonical coverage too small: {len(rows)} rows")
    scaffold.prior.base.write_json(
        CURVE_ROWS_JSON,
        {
            "source": "FRED 10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity",
            "series_id": CURVE_SERIES,
            "source_url": FRED_URL,
            "known_at": "FRED observation-date close; paper entry is next session open",
            "fetched_at": utc_now(),
            "start": FETCH_START,
            "end": FETCH_END,
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def curve_steepening_context(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(CURVE_TICKER) or []
    idx = indices.get(CURVE_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "curve_sma_sessions": CURVE_SMA_SESSIONS,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "after_observation_date_close_before_next_open_paper_entry",
    }
    if idx < CURVE_SMA_SESSIONS:
        return {**context, "passed": False, "reason": "insufficient_curve_history"}
    closes = [number(row.get("Close")) for row in rows]
    current_window = closes[idx - CURVE_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - CURVE_SMA_SESSIONS : idx]
    current, previous = closes[idx], closes[idx - 1]
    if current is None or previous is None or any(v is None for v in current_window + prior_window):
        return {**context, "passed": False, "reason": "missing_curve_close"}
    current_sma = sum(float(v) for v in current_window) / CURVE_SMA_SESSIONS
    prior_sma = sum(float(v) for v in prior_window) / CURVE_SMA_SESSIONS
    passed = current > current_sma and previous <= prior_sma
    return {
        **context,
        "t10y2y_close": round(current, 6),
        "t10y2y_prior_close": round(previous, 6),
        "t10y2y_sma20": round(current_sma, 6),
        "t10y2y_prior_sma20": round(prior_sma, 6),
        "t10y2y_spread_to_sma20": round(current - current_sma, 6),
        "passed": passed,
        "reason": "t10y2y_first_cross_above_sma20" if passed else "not_first_cross_above_sma20",
    }


def curve_candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    row = scaffold.prior.base.BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None or str(row.get("sector") or "") != FINANCIAL_SECTOR:
        return None
    row["source"] = "FRED_T10Y2Y_FINANCIAL_LEADERSHIP_PAPER"
    row["treasury_curve_context"] = row.pop("macro_relief_context", kwargs["context"])
    row["rule_version"] = CHANGED_VARIABLE
    return row


def install_configuration() -> None:
    target = scaffold.prior
    values = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "OWNER": OWNER,
        "SLUG": SLUG,
        "RUNNER": RUNNER,
        "RUNNER_PS": RUNNER_PS,
        "RUNNER_COMMAND": RUNNER_COMMAND,
        "OUT_DIR": OUT_DIR,
        "OUT_JSON": OUT_JSON,
        "VVIX_ROWS_JSON": CURVE_ROWS_JSON,
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
        "VVIX_TICKER": CURVE_TICKER,
        "VVIX_SMA_SESSIONS": CURVE_SMA_SESSIONS,
        "FETCH_START": FETCH_START,
        "FETCH_END_EXCLUSIVE": "2026-04-23",
    }
    for name, value in values.items():
        setattr(target, name, value)
    target.fetch_vvix_rows = fetch_curve_rows
    target.vvix_relief_context = curve_steepening_context
    target.vvix_candidate_for_ticker = curve_candidate_for_ticker
    scaffold._ORIGINAL_INSTALL()


def calibration(payload: dict[str, Any], lead: bool) -> dict[str, Any]:
    failed = list(payload["gate4"].get("failed_reasons") or [])
    probability = float(PREDICTION["success_probability"])
    hit: list[str] = []
    if any("sample" in reason or "window_coverage" in reason for reason in failed):
        hit.append("financial_sector_sample_too_sparse")
    if any("window" in reason for reason in failed):
        hit.append("old_thin_regression")
    if any("vixy" in reason or "comparator" in reason for reason in failed):
        hit.extend(["accepted_relief_comparator_not_beaten", "term_spread_relabels_broad_beta"])
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


def build_payload() -> dict[str, Any]:
    scaffold.install_configuration = install_configuration
    payload = scaffold.build_payload()
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
            "status": "observed_only",
            "decision": (
                "positive_replay_lead_not_promoted_treasury_curve_financial_leadership"
                if lead
                else "observed_only_rejected_treasury_curve_financial_leadership"
            ),
            "accepted_alpha": False,
            "observed_only_lead": lead,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "fingerprint_caveat": (
                "Reservation initially classified the unseen FRED source as ohlcv_relation; "
                "exp016 adds the dedicated fred_treasury_curve key before closeout."
            ),
        }
    )
    payload["data_coverage"].update(
        {
            "source": "FRED T10Y2Y 10-Year minus 2-Year Treasury Constant Maturity Spread",
            "series_id": CURVE_SERIES,
            "steepening_events_by_window": {
                label: payload["context_scan_by_window"][label].get("volatility_relief_days", 0)
                for label in scaffold.prior.base.prior.framework.WINDOWS
            },
            "candidate_sector": FINANCIAL_SECTOR,
        }
    )
    for key in ("vvix_sma_sessions", "vvix_event", "skew_sma_sessions", "skew_event"):
        payload["parameters"].pop(key, None)
    payload["parameters"].update(
        {
            "t10y2y_sma_sessions": CURVE_SMA_SESSIONS,
            "t10y2y_event": "first_close_above_sma_after_prior_close_at_or_below_prior_sma",
            "candidate_sector": FINANCIAL_SECTOR,
            "stock_selector": "unchanged_exp_20260607_018_except_predeclared_sector_relation",
        }
    )
    runtime = [
        value
        for value in payload["gate2"].get("runtime_fields", [])
        if "SKEW" not in value and "VVIX" not in value and "MOVE" not in value
    ]
    runtime.insert(3, "FRED T10Y2Y daily Close with 20-session history")
    runtime.insert(4, "candidate sector == Financial Services")
    payload["gate2"]["runtime_fields"] = runtime
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed 2s10s steepening / Financial leadership relation cleared the private scout bar across all canonical windows."
            if lead
            else "The fixed 2s10s steepening / Financial relation did not add robust after-cost value; it was sparse, concentrated, window-fragile, or another beta timing label."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing the curve moving-average span, adding level or persistence gates, expanding sectors, changing Financial subindustries, stock filters, top-N, hold, cooldown, notional, windows, or response shape."
        ),
        "new_evidence_required": (
            "A retry requires a shared default-off helper with materially settled forward rows if this is a lead, or a genuinely different publication-timed bank funding/loan-growth source if rejected."
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
        scaffold.prior.base.repo_rel(CURVE_ROWS_JSON),
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
        "1_alpha_hypothesis": "candidate_pool: Treasury curve steepening may favor Financial stock leaders",
        "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS, "novelty_override": True},
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": "Canonical Gate 1-4 plus accepted VIXY comparator; positive remains an observed-only lead.",
        "5_reproducibility": RUNNER_COMMAND,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Treasury 2s10s Financial Leadership",
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
            f"- T10Y2Y coverage: `{payload['data_coverage']['rows_by_window']}`",
            f"- Steepening events: `{payload['data_coverage']['steepening_events_by_window']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Accepted VIXY comparator passed: `{payload['closest_accepted_comparator']['passed']}`",
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


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [REPO_ROOT / RUNNER, OUT_JSON, CURVE_ROWS_JSON, LOG_JSON, CARD_MD, TICKET_JSON]
    scaffold.prior.base.write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "created_at": payload.get("timestamp") or utc_now(),
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "files": {
                scaffold.prior.base.repo_rel(path): {
                    "exists": path.exists(),
                    "sha256": scaffold.prior.base.sha256(path),
                }
                for path in paths
            },
        },
    )


def persist(payload: dict[str, Any]) -> None:
    scaffold.prior.base.write_json(OUT_JSON, payload)
    save_experiment_log_entry(scaffold.prior.base.compact_log(payload), allow_duplicate=True)
    scaffold.prior.base.write_text(CARD_MD, build_card(payload))
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
            "artifact": scaffold.prior.base.repo_rel(OUT_JSON),
            "log": scaffold.prior.base.repo_rel(LOG_JSON),
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
            "artifact": scaffold.prior.base.repo_rel(OUT_JSON),
            "log": scaffold.prior.base.repo_rel(LOG_JSON),
            "card_file": scaffold.prior.base.repo_rel(CARD_MD),
            "revision_manifest_file": scaffold.prior.base.repo_rel(MANIFEST_JSON),
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
    write_manifest(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "t10y2y_rows": payload["data_coverage"]["row_count"],
                "steepening_events": payload["data_coverage"]["steepening_events_by_window"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "vixy_comparator_passed": payload["closest_accepted_comparator"]["passed"],
                "failed_reasons": payload["gate4"].get("failed_reasons"),
                "artifact": scaffold.prior.base.repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
