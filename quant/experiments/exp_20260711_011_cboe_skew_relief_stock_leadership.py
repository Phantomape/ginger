"""exp-20260711-011: Cboe SKEW tail-risk relief stock-leadership scout.

Private replay scout on a genuinely new data source. The only decision
hypothesis is a first Cboe SKEW close below its trailing 20-session mean. The
stock selector, execution, costs, notional, top-2 budget, cooldown, and
canonical windows are frozen from exp-20260607-018.

No production, core, order, ranking, sizing, exit, or LLM behavior changes.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import exp_20260711_008_cboe_vvix_relief_stock_leadership as prior  # noqa: E402


EXPERIMENT_ID = "exp-20260711-011"
OWNER = "alpha-explore"
SLUG = "cboe_skew_relief_stock_leadership"
RUNNER = f"quant/experiments/exp_20260711_011_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_011_{SLUG}.json"
SKEW_ROWS_JSON = OUT_DIR / "cboe_skew_daily_closes.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Private replay scout: a first daily CBOE SKEW Index close below its "
    "trailing 20-session mean is an option-implied equity-tail-risk relief "
    "event; applying the unchanged exp-20260607-018 liquid stock-leadership "
    "selector should add positive next-open 10-session paper replacement "
    "value across all canonical windows and beat the accepted VIXY relief "
    "comparator without window, drawdown, survival, or concentration failure."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_new_data_shape"
MECHANISM_FAMILY = "production_visible_cboe_tail_risk_relief_candidate_pool"
TRIAL_FAMILY = "cboe_skew_relief_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "skew20_cross_below_fixed_stock_leadership_v1"
CHANGED_VARIABLE = "skew20_cross_below_tail_risk_relief_stock_leadership_v1"
NEW_EVIDENCE_TYPE = "new_data_source_cboe_skew"
NEW_EVIDENCE_AXIS = (
    "CBOE SKEW daily history is a genuinely new data source with 426 rows "
    "spanning all three canonical windows; no prior experiment used the SKEW "
    "index, while the selector and response shape remain frozen."
)
NEARBY_PRIORS = [
    "exp-20260607-018",
    "exp-20260710-020",
    "exp-20260711-001",
    "exp-20260711-002",
    "exp-20260711-008",
]
CAUSAL_COMPONENTS = [
    "Yahoo-mirrored Cboe SKEW daily closes",
    "fixed first cross below trailing 20-session simple mean",
    "unchanged exp-20260607-018 stock leadership selector",
    "next-open 10-session paper replay",
    "canonical costs and Gate 1-4",
    "accepted VIXY relief comparator",
]
PREDICTION = {
    "success_probability": 0.08,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "skew_relief_relabels_vixy_risk_on_beta",
        "accepted_vixy_comparator_not_beaten",
        "signal_too_sparse",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
        "baseline_identity_drift",
    ],
    "confidence_reason": (
        "CBOE SKEW is a genuinely new option-implied tail-risk source with "
        "complete canonical coverage and a plausible falling-tail-premium "
        "relief mechanism; odds remain low because adjacent risk-relief labels "
        "often overlap beta or fail the accepted VIXY comparator."
    ),
    "recorded_at": "2026-07-11T06:05:44Z",
}
PRODUCTION_IMPACT = dict(prior.PRODUCTION_IMPACT)
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

SKEW_TICKER = "SKEW"
FETCH_START = "2024-08-01"
FETCH_END_EXCLUSIVE = "2026-04-23"
SKEW_SMA_SESSIONS = 20
_ORIGINAL_INSTALL = prior.install_base_configuration


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fetch_skew_rows() -> list[dict[str, Any]]:
    if SKEW_ROWS_JSON.exists():
        cached = json.loads(SKEW_ROWS_JSON.read_text(encoding="utf-8"))
        if cached.get("rows"):
            return list(cached["rows"])
    frame = prior.base.download_with_rate_limit_retry(
        "^SKEW",
        start=FETCH_START,
        end=FETCH_END_EXCLUSIVE,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if frame is None or getattr(frame, "empty", True):
        raise RuntimeError("Cboe SKEW history is unavailable")
    rows: list[dict[str, Any]] = []
    for stamp in frame.index:
        row: dict[str, Any] = {"Date": str(stamp)[:10], "Volume": 0.0}
        complete = True
        for field in ("Open", "High", "Low", "Close"):
            values = frame[field]
            if hasattr(values, "columns"):
                values = values.iloc[:, 0]
            value = number(values.loc[stamp])
            if value is None:
                complete = False
                break
            row[field] = value
        if complete:
            rows.append(row)
    if len(rows) < 400:
        raise RuntimeError(f"SKEW canonical coverage too small: {len(rows)} rows")
    prior.base.write_json(
        SKEW_ROWS_JSON,
        {
            "source": "Yahoo Finance mirror of Cboe SKEW Index",
            "delivery_ticker": "^SKEW",
            "known_at": "each row close after its session",
            "fetched_at": utc_now(),
            "start": FETCH_START,
            "end_exclusive": FETCH_END_EXCLUSIVE,
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def skew_relief_context(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(SKEW_TICKER) or []
    idx = indices.get(SKEW_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "skew_sma_sessions": SKEW_SMA_SESSIONS,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if idx < SKEW_SMA_SESSIONS:
        return {**context, "passed": False, "reason": "insufficient_skew_history"}
    closes = [number(row.get("Close")) for row in rows]
    current_window = closes[idx - SKEW_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - SKEW_SMA_SESSIONS : idx]
    current, previous = closes[idx], closes[idx - 1]
    if current is None or previous is None or any(v is None for v in current_window + prior_window):
        return {**context, "passed": False, "reason": "missing_skew_close"}
    current_sma = sum(float(v) for v in current_window) / SKEW_SMA_SESSIONS
    prior_sma = sum(float(v) for v in prior_window) / SKEW_SMA_SESSIONS
    passed = current < current_sma and previous >= prior_sma
    return {
        **context,
        "skew_close": round(current, 6),
        "skew_prior_close": round(previous, 6),
        "skew_sma20": round(current_sma, 6),
        "skew_prior_sma20": round(prior_sma, 6),
        "skew_discount_to_sma20": round(current / current_sma - 1.0, 6),
        "passed": passed,
        "reason": "skew_first_cross_below_sma20" if passed else "not_first_cross_below_sma20",
    }


def skew_candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    row = prior.base.BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None:
        return None
    row["source"] = "CBOE_SKEW_RELIEF_LEADERSHIP_PAPER"
    row["cboe_skew_relief_context"] = row.pop("macro_relief_context", kwargs["context"])
    row["rule_version"] = CHANGED_VARIABLE
    return row


def install_configuration() -> None:
    values = {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "OWNER": OWNER,
        "SLUG": SLUG,
        "RUNNER": RUNNER,
        "RUNNER_PS": RUNNER_PS,
        "RUNNER_COMMAND": RUNNER_COMMAND,
        "OUT_DIR": OUT_DIR,
        "OUT_JSON": OUT_JSON,
        "VVIX_ROWS_JSON": SKEW_ROWS_JSON,
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
        "VVIX_TICKER": SKEW_TICKER,
        "VVIX_SMA_SESSIONS": SKEW_SMA_SESSIONS,
        "FETCH_START": FETCH_START,
        "FETCH_END_EXCLUSIVE": FETCH_END_EXCLUSIVE,
    }
    for name, value in values.items():
        setattr(prior, name, value)
    prior.fetch_vvix_rows = fetch_skew_rows
    prior.vvix_relief_context = skew_relief_context
    prior.vvix_candidate_for_ticker = skew_candidate_for_ticker
    _ORIGINAL_INSTALL()


def calibration(payload: dict[str, Any], lead: bool) -> dict[str, Any]:
    failed = list(payload["gate4"].get("failed_reasons") or [])
    probability = float(PREDICTION["success_probability"])
    hit: list[str] = []
    if any("vixy" in reason for reason in failed):
        hit.extend(["accepted_vixy_comparator_not_beaten", "skew_relief_relabels_vixy_risk_on_beta"])
    if any("window" in reason for reason in failed):
        hit.append("window_regression")
    if any("drawdown" in reason for reason in failed):
        hit.append("drawdown_drift")
    if any("concentration" in reason for reason in failed):
        hit.append("concentration_failed")
    if any("sample" in reason or "coverage" in reason for reason in failed):
        hit.append("signal_too_sparse")
    return {
        "predicted_success_probability": probability,
        "actual_success": lead,
        "brier_score": round((probability - (1.0 if lead else 0.0)) ** 2, 6),
        "predicted_failure_modes": list(PREDICTION["main_failure_modes"]),
        "predicted_failure_modes_hit": sorted(set(hit)),
        "failed_reasons": failed,
    }


def build_payload() -> dict[str, Any]:
    prior.install_base_configuration = install_configuration
    payload = prior.build_payload()
    lead = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "hypothesis": HYPOTHESIS,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "decision": (
                "positive_replay_lead_not_promoted_cboe_skew_relief"
                if lead
                else "observed_only_rejected_cboe_skew_relief"
            ),
            "observed_only_lead": lead,
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "fingerprint_caveat": (
                "Reservation overmatched forward_replacement_value; exp011 "
                "adds cboe_skew and rebuilds frozen families."
            ),
        }
    )
    payload["data_coverage"].update(
        {
            "source": "Yahoo Finance mirror of Cboe SKEW Index",
            "relief_events_by_window": {
                label: payload["context_scan_by_window"][label].get("volatility_relief_days", 0)
                for label in prior.base.prior.framework.WINDOWS
            },
        }
    )
    payload["parameters"].pop("vvix_sma_sessions", None)
    payload["parameters"].pop("vvix_event", None)
    payload["parameters"].update(
        {
            "skew_sma_sessions": SKEW_SMA_SESSIONS,
            "skew_event": "first_close_below_sma_after_prior_close_at_or_above_prior_sma",
            "stock_selector": "unchanged_exp_20260607_018",
        }
    )
    payload["gate2"]["runtime_fields"] = [
        value.replace("Cboe VVIX", "Cboe SKEW")
        for value in payload["gate2"].get("runtime_fields", [])
    ]
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "SKEW relief beat both the canonical core and accepted VIXY relief comparator across every window."
            if lead
            else "The fixed SKEW relief event did not add incremental evidence over accepted VIXY relief after costs; it was sparse, window-fragile, or another equity risk-on beta label."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing the SKEW moving-average span, adding levels or persistence, changing stock filters, top-N, hold, cooldown, notional, windows, or response shape."
        ),
        "new_evidence_required": (
            "Reopen only with materially settled prospective rows from a fixed shared helper or a genuinely different publication-timed option-implied tail-risk source."
        ),
    }
    payload["calibration"] = calibration(payload, lead)
    payload["rejection_reason"] = (
        None if lead else ";".join(payload["gate4"].get("failed_reasons") or ["gate4_not_passed"])
    )
    payload["related_files"] = [
        RUNNER,
        "quant/experiments/exp_20260607_018_volatility_relief_stock_leadership.py",
        prior.base.repo_rel(SKEW_ROWS_JSON),
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
        "1_alpha_hypothesis": "candidate_pool: falling option-implied tail premium may identify durable liquid stock leadership",
        "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS, "novelty_override": True},
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": "Canonical Gate 1-4 plus explicit accepted VIXY relief comparator report.",
        "5_reproducibility": RUNNER_COMMAND,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Cboe SKEW Relief Replay",
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
            f"- SKEW coverage: `{payload['data_coverage']['rows_by_window']}`",
            f"- SKEW relief events: `{payload['data_coverage']['relief_events_by_window']}`",
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
    prior.base.build_card = build_card
    prior.base.persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.JSONEncoder(indent=2, sort_keys=True).encode(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "skew_rows": payload["data_coverage"]["row_count"],
                "skew_relief_events": payload["data_coverage"]["relief_events_by_window"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "vixy_comparator_passed": payload["closest_accepted_comparator"]["passed"],
                "failed_reasons": payload["gate4"].get("failed_reasons"),
                "artifact": prior.base.repo_rel(OUT_JSON),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
