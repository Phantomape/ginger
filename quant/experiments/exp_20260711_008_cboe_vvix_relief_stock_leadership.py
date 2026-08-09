"""exp-20260711-008: Cboe VVIX relief stock-leadership scout.

Private replay scout on a genuinely new data source. The only decision
hypothesis is a first Cboe VVIX close below its trailing 20-session simple
mean. The stock selector, execution, costs, notional, top-2 budget, cooldown,
and canonical windows are frozen from exp-20260607-018.

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

import exp_20260711_002_move_rate_volatility_relief_stock_leadership as base  # noqa: E402


EXPERIMENT_ID = "exp-20260711-008"
OWNER = "alpha-explore"
SLUG = "cboe_vvix_relief_stock_leadership"
RUNNER = f"quant/experiments/exp_20260711_008_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_008_{SLUG}.json"
VVIX_ROWS_JSON = OUT_DIR / "cboe_vvix_daily_closes.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Private replay scout: a first daily CBOE VVIX close below its trailing "
    "20-session mean is an equity vol-of-vol relief event; applying the "
    "unchanged exp-20260607-018 liquid stock-leadership selector should add "
    "positive next-open 10-session paper replacement value across all "
    "canonical windows and beat the accepted VIXY relief comparator without "
    "window, drawdown, survival, or concentration failure."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_new_data_shape"
MECHANISM_FAMILY = "production_visible_cboe_vol_of_vol_relief_candidate_pool"
TRIAL_FAMILY = "cboe_vvix_relief_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "vvix20_cross_below_fixed_stock_leadership_v1"
CHANGED_VARIABLE = "vvix20_cross_below_vol_of_vol_relief_stock_leadership_v1"
NEW_EVIDENCE_TYPE = "new_data_source_cboe_vvix"
NEW_EVIDENCE_AXIS = (
    "CBOE VVIX daily history spans all three canonical windows and no prior "
    "experiment used VVIX equity vol-of-vol relief; the response shape and "
    "stock selector remain frozen rather than retuned."
)
NEARBY_PRIORS = [
    "exp-20260607-018",
    "exp-20260607-026",
    "exp-20260609-022",
    "exp-20260710-020",
    "exp-20260711-002",
]
CAUSAL_COMPONENTS = [
    "Yahoo-mirrored Cboe VVIX daily closes",
    "fixed first cross below trailing 20-session simple mean",
    "unchanged exp-20260607-018 stock leadership selector",
    "next-open 10-session paper replay",
    "canonical costs and Gate 1-4",
    "accepted VIXY relief comparator",
]
PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "vvix_relief_relabels_vixy_risk_on_beta",
        "accepted_vixy_comparator_not_beaten",
        "signal_too_sparse",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
        "baseline_identity_drift",
    ],
    "confidence_reason": (
        "VVIX is a genuinely new options-implied equity uncertainty source "
        "with complete canonical coverage, and MOVE/VIXY relief support the "
        "mechanism; odds remain low because adjacent macro/volatility labels "
        "often overlap beta or fail accepted comparators."
    ),
    "recorded_at": "2026-07-11T04:08:22+00:00",
}
PRODUCTION_IMPACT = dict(base.PRODUCTION_IMPACT)
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

VVIX_TICKER = "VVIX"
FETCH_START = "2024-08-01"
FETCH_END_EXCLUSIVE = "2026-04-23"
VVIX_SMA_SESSIONS = 20
VIXY_COMPARATOR = {
    "experiment_id": "exp-20260607-018",
    "aggregate_ev_delta": 0.5732,
    "aggregate_pnl_delta": 11934.79,
    "by_window": {
        "late_strong": {"expected_value_score": 0.2388, "total_pnl": 2165.40},
        "mid_weak": {"expected_value_score": 0.2173, "total_pnl": 4898.38},
        "old_thin": {"expected_value_score": 0.1171, "total_pnl": 4871.01},
    },
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fetch_vvix_rows() -> list[dict[str, Any]]:
    if VVIX_ROWS_JSON.exists():
        cached = json.loads(VVIX_ROWS_JSON.read_text(encoding="utf-8"))
        if cached.get("rows"):
            return list(cached["rows"])
    frame = base.download_with_rate_limit_retry(
        "^VVIX",
        start=FETCH_START,
        end=FETCH_END_EXCLUSIVE,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if frame is None or getattr(frame, "empty", True):
        raise RuntimeError("Cboe VVIX history is unavailable")
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
        raise RuntimeError(f"VVIX canonical coverage too small: {len(rows)} rows")
    base.write_json(
        VVIX_ROWS_JSON,
        {
            "source": "Yahoo Finance mirror of Cboe VVIX Index",
            "delivery_ticker": "^VVIX",
            "known_at": "each row close after its session",
            "fetched_at": utc_now(),
            "start": FETCH_START,
            "end_exclusive": FETCH_END_EXCLUSIVE,
            "row_count": len(rows),
            "rows": rows,
        },
    )
    return rows


def vvix_relief_context(snapshot: dict[str, list[dict[str, Any]]], indices: dict[str, dict[str, int]], signal_date: str) -> dict[str, Any] | None:
    rows = snapshot.get(VVIX_TICKER) or []
    idx = indices.get(VVIX_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "vvix_sma_sessions": VVIX_SMA_SESSIONS,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if idx < VVIX_SMA_SESSIONS:
        return {**context, "passed": False, "reason": "insufficient_vvix_history"}
    closes = [number(row.get("Close")) for row in rows]
    current_window = closes[idx - VVIX_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - VVIX_SMA_SESSIONS : idx]
    current, previous = closes[idx], closes[idx - 1]
    if current is None or previous is None or any(v is None for v in current_window + prior_window):
        return {**context, "passed": False, "reason": "missing_vvix_close"}
    current_sma = sum(float(v) for v in current_window) / VVIX_SMA_SESSIONS
    prior_sma = sum(float(v) for v in prior_window) / VVIX_SMA_SESSIONS
    passed = current < current_sma and previous >= prior_sma
    return {
        **context,
        "vvix_close": round(current, 6),
        "vvix_prior_close": round(previous, 6),
        "vvix_sma20": round(current_sma, 6),
        "vvix_prior_sma20": round(prior_sma, 6),
        "vvix_discount_to_sma20": round(current / current_sma - 1.0, 6),
        "passed": passed,
        "reason": "vvix_first_cross_below_sma20" if passed else "not_first_cross_below_sma20",
    }


def vvix_candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    row = base.BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None:
        return None
    row["source"] = "CBOE_VVIX_RELIEF_LEADERSHIP_PAPER"
    row["cboe_vvix_relief_context"] = row.pop("macro_relief_context", kwargs["context"])
    row["rule_version"] = CHANGED_VARIABLE
    return row


def install_base_configuration() -> None:
    values = {
        "EXPERIMENT_ID": EXPERIMENT_ID, "OWNER": OWNER, "SLUG": SLUG,
        "RUNNER": RUNNER, "RUNNER_PS": RUNNER_PS, "RUNNER_COMMAND": RUNNER_COMMAND,
        "OUT_DIR": OUT_DIR, "OUT_JSON": OUT_JSON, "MOVE_ROWS_JSON": VVIX_ROWS_JSON,
        "LOG_JSON": LOG_JSON, "CARD_MD": CARD_MD, "MANIFEST_JSON": MANIFEST_JSON,
        "TICKET_JSON": TICKET_JSON, "REGISTRY_JSON": REGISTRY_JSON,
        "HYPOTHESIS": HYPOTHESIS, "CHANGE_TYPE": CHANGE_TYPE,
        "IMPLEMENTATION_MODE": IMPLEMENTATION_MODE, "MECHANISM_FAMILY": MECHANISM_FAMILY,
        "TRIAL_FAMILY": TRIAL_FAMILY, "TRIAL_VARIANT_ID": TRIAL_VARIANT_ID,
        "CHANGED_VARIABLE": CHANGED_VARIABLE, "NEW_EVIDENCE_TYPE": NEW_EVIDENCE_TYPE,
        "NEW_EVIDENCE_AXIS": NEW_EVIDENCE_AXIS, "NEARBY_PRIORS": NEARBY_PRIORS,
        "CAUSAL_COMPONENTS": CAUSAL_COMPONENTS, "PREDICTION": PREDICTION,
        "PRODUCTION_IMPACT": PRODUCTION_IMPACT, "ALLOWED_WRITE_SCOPE": ALLOWED_WRITE_SCOPE,
        "MOVE_TICKER": VVIX_TICKER, "MOVE_SMA_SESSIONS": VVIX_SMA_SESSIONS,
        "FETCH_START": FETCH_START, "FETCH_END_EXCLUSIVE": FETCH_END_EXCLUSIVE,
    }
    for name, value in values.items():
        setattr(base, name, value)
    base.fetch_move_rows = fetch_vvix_rows
    base.move_relief_context = vvix_relief_context
    base.candidate_for_ticker = vvix_candidate_for_ticker


def comparator_block(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    by_window = payload["delta_metrics"]["by_window"]
    checks = {
        "aggregate_ev_beats_vixy": aggregate["expected_value_score_delta_sum"] > VIXY_COMPARATOR["aggregate_ev_delta"],
        "aggregate_pnl_beats_vixy": aggregate["total_pnl_delta_sum"] > VIXY_COMPARATOR["aggregate_pnl_delta"],
    }
    for label, expected in VIXY_COMPARATOR["by_window"].items():
        checks[f"{label}_ev_beats_vixy"] = by_window[label]["expected_value_score"] > expected["expected_value_score"]
        checks[f"{label}_pnl_beats_vixy"] = by_window[label]["total_pnl"] > expected["total_pnl"]
    return {"comparator": VIXY_COMPARATOR, "checks": checks, "passed": all(checks.values())}


def calibration(payload: dict[str, Any], lead: bool) -> dict[str, Any]:
    failed = list(payload["gate4"].get("failed_reasons") or [])
    hit = [mode for mode in PREDICTION["main_failure_modes"] if (
        (mode == "accepted_vixy_comparator_not_beaten" and any("vixy" in x for x in failed))
        or (mode == "window_regression" and any("window" in x for x in failed))
        or (mode == "drawdown_drift" and any("drawdown" in x for x in failed))
        or (mode == "concentration_failed" and any("concentration" in x for x in failed))
        or (mode == "signal_too_sparse" and any("sample" in x or "coverage" in x for x in failed))
        or (mode == "baseline_identity_drift" and any("gate1" in x for x in failed))
    )]
    probability = float(PREDICTION["success_probability"])
    return {
        "predicted_success_probability": probability,
        "actual_success": lead,
        "brier_score": round((probability - (1.0 if lead else 0.0)) ** 2, 6),
        "predicted_failure_modes": list(PREDICTION["main_failure_modes"]),
        "predicted_failure_modes_hit": hit,
        "failed_reasons": failed,
    }


def build_payload() -> dict[str, Any]:
    install_base_configuration()
    payload = base.build_payload()
    comparator = comparator_block(payload)
    payload["closest_accepted_comparator"] = comparator
    if not comparator["passed"]:
        failed = payload["gate4"].setdefault("failed_reasons", [])
        if "accepted_vixy_comparator_not_beaten" not in failed:
            failed.append("accepted_vixy_comparator_not_beaten")
        payload["gate4"]["passed"] = False
    lead = bool(payload["gate4"]["passed"])
    payload.update({
        "hypothesis": HYPOTHESIS,
        "mechanism_family": MECHANISM_FAMILY,
        "decision": "positive_replay_lead_not_promoted_cboe_vvix_relief" if lead else "observed_only_rejected_cboe_vvix_relief",
        "observed_only_lead": lead,
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "fingerprint_caveat": "Reservation overmatched forward_replacement_value; exp008 adds cboe_vvix and rebuilds frozen families.",
    })
    payload["data_coverage"].update({
        "source": "Yahoo Finance mirror of Cboe VVIX Index",
        "relief_events_by_window": {
            label: payload["context_scan_by_window"][label].get("volatility_relief_days", 0)
            for label in base.prior.framework.WINDOWS
        },
    })
    payload["parameters"].pop("move_sma_sessions", None)
    payload["parameters"].pop("move_event", None)
    payload["parameters"].update({
        "vvix_sma_sessions": VVIX_SMA_SESSIONS,
        "vvix_event": "first_close_below_sma_after_prior_close_at_or_above_prior_sma",
        "stock_selector": "unchanged_exp_20260607_018",
    })
    runtime = [x for x in payload["gate2"].get("runtime_fields", []) if "MOVE" not in x]
    runtime.insert(3, "Cboe VVIX daily Close with 20-session history")
    payload["gate2"]["runtime_fields"] = runtime
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "VVIX relief beat both the canonical core and the accepted VIXY relief comparator across every window."
            if lead else
            "The fixed VVIX relief event did not provide incremental evidence over accepted VIXY relief after costs; it was sparse, window-fragile, or another equity risk-on beta label."
        ),
        "forbidden_near_neighbor_retry": "Do not retry by changing the VVIX moving-average span, adding levels or persistence, changing stock filters, top-N, hold, cooldown, notional, windows, or response shape.",
        "new_evidence_required": "Reopen only with materially settled prospective rows from a fixed shared helper or a genuinely different option-implied uncertainty source with publication-timed PIT provenance.",
    }
    payload["calibration"] = calibration(payload, lead)
    payload["rejection_reason"] = None if lead else ";".join(payload["gate4"].get("failed_reasons") or ["gate4_not_passed"])
    payload["related_files"] = [RUNNER, "quant/experiments/exp_20260607_018_volatility_relief_stock_leadership.py", base.repo_rel(VVIX_ROWS_JSON), "scripts/experiment_fingerprint.py", "quant/test_experiment_fingerprint.py"]
    payload["changed_files"] = ALLOWED_WRITE_SCOPE
    payload["reproduction_commands"] = [
        f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
        RUNNER_COMMAND,
        ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
        ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
        ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
    ]
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": "candidate_pool: equity vol-of-vol relief may identify durable liquid stock leadership",
        "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS, "novelty_override": True},
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": "Canonical Gate 1-4 plus explicit accepted VIXY relief comparator report.",
        "5_reproducibility": RUNNER_COMMAND,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join([
        f"# {EXPERIMENT_ID} Cboe VVIX Relief Replay", "",
        f"Status: `{payload['status']}`", f"Decision: `{payload['decision']}`", "",
        "## Hypothesis", "", HYPOTHESIS, "", "## Result", "",
        f"- VVIX coverage: `{payload['data_coverage']['rows_by_window']}`",
        f"- VVIX relief events: `{payload['data_coverage']['relief_events_by_window']}`",
        f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
        f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
        f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
        f"- Accepted VIXY comparator passed: `{payload['closest_accepted_comparator']['passed']}`",
        f"- Failed gates: `{payload['gate4'].get('failed_reasons') or 'none'}`", "",
        "## Reflection", "", payload["post_run_reflection"]["why_result_happened"], "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"], "",
    ])


def main() -> int:
    payload = build_payload()
    base.build_card = build_card
    base.persist(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(json.JSONEncoder(indent=2, sort_keys=True).encode({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "vvix_rows": payload["data_coverage"]["row_count"],
        "vvix_relief_events": payload["data_coverage"]["relief_events_by_window"],
        "target_trades": payload["target_trade_summary"]["total_trade_count"],
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "vixy_comparator_passed": payload["closest_accepted_comparator"]["passed"],
        "failed_reasons": payload["gate4"].get("failed_reasons"),
        "artifact": base.repo_rel(OUT_JSON),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
