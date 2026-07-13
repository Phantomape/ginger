"""exp-20260711-013: direct high-yield OAS credit-relief full-stack gate.

The fixed decision hypothesis is the first ICE BofA US high-yield option-
adjusted spread close below its trailing 20-session mean.  The stock selector,
execution, costs, notional, top-2 budget, cooldown, and canonical windows are
frozen from exp-20260607-018.  A positive Gate-4 read must be completed with a
shared default-off helper and daily parity in this same experiment before it
can be persisted as accepted paper alpha.
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


EXPERIMENT_ID = "exp-20260711-013"
OWNER = "alpha-explore"
SLUG = "high_yield_oas_credit_relief_shared_paper"
RUNNER = f"quant/experiments/exp_20260711_013_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_013_{SLUG}.json"
OAS_ROWS_JSON = OUT_DIR / "fred_ice_bofa_high_yield_oas_daily.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "candidate_pool/full_stack: the first ICE BofA US high-yield OAS close "
    "below its trailing 20-session mean is direct credit-risk relief; the "
    "unchanged liquid stock-leadership selector should add next-open "
    "10-session replacement value across all canonical windows and beat the "
    "closest accepted relief comparator without drawdown, survival, or "
    "concentration failure."
)
CHANGE_TYPE = "candidate_pool_full_stack"
IMPLEMENTATION_MODE = "shared_paper_first_gate4_before_retention"
MECHANISM_FAMILY = "production_visible_direct_credit_spread_relief_candidate_pool"
TRIAL_FAMILY = "high_yield_oas_credit_relief_shared_paper_candidate_pool"
TRIAL_VARIANT_ID = "fred_bamlh0a0hym2_oas20_cross_below_top2_10d_v1"
CHANGED_VARIABLE = "fred_high_yield_oas20_first_cross_below_credit_relief_shared_paper_v1"
NEW_EVIDENCE_TYPE = "new_data_source_fred_high_yield_oas"
NEW_EVIDENCE_AXIS = (
    "New data source: FRED BAMLH0A0HYM2 is the direct ICE BofA US high-yield "
    "option-adjusted spread with 452 PIT canonical-span rows; exp-20260711-001 "
    "explicitly required a genuinely different credit-risk-transfer source "
    "after the HYG/JNK proxy rejection."
)
NEARBY_PRIORS = [
    "exp-20260711-001",
    "exp-20260607-020",
    "exp-20260711-004",
    "exp-20260607-018",
]
CAUSAL_COMPONENTS = [
    "FRED ICE BofA US high-yield OAS daily observations",
    "fixed first cross below trailing 20-session simple mean",
    "unchanged exp-20260607-018 stock leadership selector",
    "next-open 10-session paper replay",
    "canonical costs and Gate 1-4",
    "accepted VIXY relief comparator",
    "shared helper and daily snapshot retained only after Gate 4 passes",
]
PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "credit_relief_relabels_equity_beta",
        "accepted_relief_comparator_not_beaten",
        "old_thin_window_regression",
        "drawdown_drift",
        "fred_daily_fetch_unavailable",
    ],
    "confidence_reason": (
        "Direct ICE BofA high-yield option-adjusted spread compression removes "
        "the duration and ETF-flow noise that weakened HYG/JNK proxies, while "
        "452 PIT observations cover the canonical span; odds remain low because "
        "recent macro relief sources usually relabeled broad beta and the "
        "accepted relief comparator is demanding."
    ),
    "recorded_at": "2026-07-11T07:06:05Z",
}
PRODUCTION_IMPACT = dict(scaffold.PRODUCTION_IMPACT)
PRODUCTION_IMPACT.update(
    {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "trade_enabled": False,
        "scope": "gate4_before_shared_helper_retention",
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

OAS_TICKER = "HY_OAS"
OAS_SERIES = "BAMLH0A0HYM2"
FRED_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={OAS_SERIES}"
FETCH_START = "2024-08-01"
FETCH_END = "2026-04-22"
OAS_SMA_SESSIONS = 20


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fetch_oas_rows() -> list[dict[str, Any]]:
    if OAS_ROWS_JSON.exists():
        cached = json.loads(OAS_ROWS_JSON.read_text(encoding="utf-8"))
        if cached.get("rows"):
            return list(cached["rows"])
    with urllib.request.urlopen(FRED_URL, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    rows: list[dict[str, Any]] = []
    for source in csv.DictReader(io.StringIO(text)):
        day = str(source.get("observation_date") or "")[:10]
        value = number(source.get(OAS_SERIES))
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
        raise RuntimeError(f"FRED high-yield OAS canonical coverage too small: {len(rows)} rows")
    scaffold.prior.base.write_json(
        OAS_ROWS_JSON,
        {
            "source": "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
            "series_id": OAS_SERIES,
            "source_url": FRED_URL,
            "known_at": "FRED observation date close; signal acts only at next session open",
            "fetched_at": utc_now(),
            "start": FETCH_START,
            "end": FETCH_END,
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def oas_relief_context(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(OAS_TICKER) or []
    idx = indices.get(OAS_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "oas_sma_sessions": OAS_SMA_SESSIONS,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "after_observation_date_close_before_next_open_paper_entry",
    }
    if idx < OAS_SMA_SESSIONS:
        return {**context, "passed": False, "reason": "insufficient_oas_history"}
    closes = [number(row.get("Close")) for row in rows]
    current_window = closes[idx - OAS_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - OAS_SMA_SESSIONS : idx]
    current, previous = closes[idx], closes[idx - 1]
    if current is None or previous is None or any(v is None for v in current_window + prior_window):
        return {**context, "passed": False, "reason": "missing_oas_close"}
    current_sma = sum(float(v) for v in current_window) / OAS_SMA_SESSIONS
    prior_sma = sum(float(v) for v in prior_window) / OAS_SMA_SESSIONS
    passed = current < current_sma and previous >= prior_sma
    return {
        **context,
        "oas_close": round(current, 6),
        "oas_prior_close": round(previous, 6),
        "oas_sma20": round(current_sma, 6),
        "oas_prior_sma20": round(prior_sma, 6),
        "oas_discount_to_sma20": round(current / current_sma - 1.0, 6),
        "passed": passed,
        "reason": "oas_first_cross_below_sma20" if passed else "not_first_cross_below_sma20",
    }


def oas_candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    row = scaffold.prior.base.BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None:
        return None
    row["source"] = "FRED_HIGH_YIELD_OAS_RELIEF_LEADERSHIP_PAPER"
    row["high_yield_oas_relief_context"] = row.pop("macro_relief_context", kwargs["context"])
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
        "VVIX_ROWS_JSON": OAS_ROWS_JSON,
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
        "VVIX_TICKER": OAS_TICKER,
        "VVIX_SMA_SESSIONS": OAS_SMA_SESSIONS,
        "FETCH_START": FETCH_START,
        "FETCH_END_EXCLUSIVE": "2026-04-23",
    }
    for name, value in values.items():
        setattr(target, name, value)
    target.fetch_vvix_rows = fetch_oas_rows
    target.vvix_relief_context = oas_relief_context
    target.vvix_candidate_for_ticker = oas_candidate_for_ticker
    scaffold._ORIGINAL_INSTALL()


def calibration(payload: dict[str, Any], accepted: bool) -> dict[str, Any]:
    failed = list(payload["gate4"].get("failed_reasons") or [])
    probability = float(PREDICTION["success_probability"])
    hit: list[str] = []
    if any("vixy" in reason or "comparator" in reason for reason in failed):
        hit.extend(["accepted_relief_comparator_not_beaten", "credit_relief_relabels_equity_beta"])
    if any("window" in reason for reason in failed):
        hit.append("old_thin_window_regression")
    if any("drawdown" in reason for reason in failed):
        hit.append("drawdown_drift")
    return {
        "predicted_success_probability": probability,
        "actual_success": accepted,
        "brier_score": round((probability - (1.0 if accepted else 0.0)) ** 2, 6),
        "predicted_failure_modes": list(PREDICTION["main_failure_modes"]),
        "predicted_failure_modes_hit": sorted(set(hit)),
        "failed_reasons": failed,
    }


def build_payload() -> dict[str, Any]:
    scaffold.install_configuration = install_configuration
    payload = scaffold.build_payload()
    gate4_passed = bool(payload["gate4"]["passed"])
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
            "status": "accepted" if gate4_passed else "rejected",
            "decision": (
                "gate4_positive_requires_same_id_shared_helper_completion"
                if gate4_passed
                else "rejected_high_yield_oas_credit_relief_shared_paper"
            ),
            "accepted_alpha": False,
            "observed_only_lead": False,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "fingerprint_caveat": (
                "Reservation initially classified the direct FRED OAS source as credit_risk_etf; "
                "exp013 added the dedicated direct_credit_spread key before closeout."
            ),
        }
    )
    payload["data_coverage"].update(
        {
            "source": "FRED ICE BofA US High Yield Index Option-Adjusted Spread",
            "series_id": OAS_SERIES,
            "relief_events_by_window": {
                label: payload["context_scan_by_window"][label].get("volatility_relief_days", 0)
                for label in scaffold.prior.base.prior.framework.WINDOWS
            },
        }
    )
    for key in ("vvix_sma_sessions", "vvix_event", "skew_sma_sessions", "skew_event"):
        payload["parameters"].pop(key, None)
    payload["parameters"].update(
        {
            "oas_sma_sessions": OAS_SMA_SESSIONS,
            "oas_event": "first_close_below_sma_after_prior_close_at_or_above_prior_sma",
            "stock_selector": "unchanged_exp_20260607_018",
        }
    )
    runtime = [
        value
        for value in payload["gate2"].get("runtime_fields", [])
        if "SKEW" not in value and "VVIX" not in value and "MOVE" not in value
    ]
    runtime.insert(3, "FRED ICE BofA high-yield OAS daily Close with 20-session history")
    payload["gate2"]["runtime_fields"] = runtime
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The direct OAS relief bundle cleared Gate 4; shared-helper retention is still required before acceptance."
            if gate4_passed
            else "Direct high-yield OAS compression did not add robust incremental value over the accepted relief comparator after costs; it remained beta-like or window fragile."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing the OAS moving-average span, adding spread levels or persistence, changing stock filters, top-N, hold, cooldown, notional, windows, or response shape."
        ),
        "new_evidence_required": (
            "Reopen only with materially settled prospective rows from a fixed shared helper, a different publication-timed credit-risk-transfer source, or a predeclared different candidate-source family."
        ),
    }
    payload["calibration"] = calibration(payload, gate4_passed)
    payload["rejection_reason"] = (
        None if gate4_passed else ";".join(payload["gate4"].get("failed_reasons") or ["gate4_not_passed"])
    )
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["related_files"] = [
        RUNNER,
        "quant/experiments/exp_20260607_018_volatility_relief_stock_leadership.py",
        scaffold.prior.base.repo_rel(OAS_ROWS_JSON),
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
        "1_alpha_hypothesis": "candidate_pool/full_stack: direct high-yield OAS compression may identify durable liquid stock leadership",
        "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS, "novelty_override": True},
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": "Canonical Gate 1-4 plus explicit accepted VIXY relief comparator; a positive read must complete shared-paper-first inside this ID.",
        "5_reproducibility": RUNNER_COMMAND,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Direct High-Yield OAS Relief",
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
            f"- OAS coverage: `{payload['data_coverage']['rows_by_window']}`",
            f"- OAS relief events: `{payload['data_coverage']['relief_events_by_window']}`",
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


def main() -> int:
    payload = build_payload()
    if payload["gate4"]["passed"]:
        raise RuntimeError(
            "Gate 4 passed; complete the shared helper, daily snapshot, and parity test under exp-20260711-013 before persisting acceptance."
        )
    scaffold.prior.base.build_card = build_card
    scaffold.prior.base.persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.JSONEncoder(indent=2, sort_keys=True).encode(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "oas_rows": payload["data_coverage"]["row_count"],
                "oas_relief_events": payload["data_coverage"]["relief_events_by_window"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "vixy_comparator_passed": payload["closest_accepted_comparator"]["passed"],
                "failed_reasons": payload["gate4"].get("failed_reasons"),
                "artifact": scaffold.prior.base.repo_rel(OUT_JSON),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
