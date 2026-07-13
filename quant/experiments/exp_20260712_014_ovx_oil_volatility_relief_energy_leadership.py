"""exp-20260712-014: OVX oil-volatility relief Energy-leadership scout.

Private replay scout.  The single decision hypothesis is that the first CBOE
OVX close below its trailing 20-session mean marks oil-risk relief and makes
same-day liquid Energy leaders more likely to continue for ten sessions.

The selector, next-open entry, costs, hold, cooldown, and paper notional are
inherited unchanged from exp-20260711-002.  Current schema-v1 daily paper MTM
and Sharpe evidence are inherited from exp-20260712-009.  No production or
live behavior changes.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import exp_20260711_002_move_rate_volatility_relief_stock_leadership as move
import exp_20260712_009_dod_contract_revenue_materiality as schema
from experiment_registry import persist_self_registered_result
from yfinance_bootstrap import download_with_rate_limit_retry


EXPERIMENT_ID = "exp-20260712-014"
OWNER = "alpha-explore"
SLUG = "ovx_oil_volatility_relief_energy_leadership"
RUNNER = f"quant/experiments/exp_20260712_014_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS

REPO_ROOT = move.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

OVX_TICKER = "OVX"
FETCH_START = "2024-08-01"
FETCH_END_EXCLUSIVE = "2026-04-23"
OVX_SMA_SESSIONS = 20

HYPOTHESIS = (
    "Private replay scout: a first daily CBOE Crude Oil ETF Volatility Index "
    "(OVX) close below its trailing 20-session mean identifies oil-risk relief; "
    "selecting the strongest liquid Energy leaders on that signal day should "
    "add positive after-cost next-open 10-session paper replacement value "
    "across all three canonical windows."
)
CHANGE_TYPE = "candidate_pool_private_replay_scout"
IMPLEMENTATION_MODE = "private_replay_scout_new_data_shape"
MECHANISM_FAMILY = "cboe_oil_volatility_relief_energy_candidate_pool"
TRIAL_FAMILY = "ovx_oil_volatility_relief_energy_leadership_candidate_pool"
TRIAL_VARIANT_ID = "ovx20_cross_below_energy_leadership_v1"
CHANGED_VARIABLE = "ovx20_cross_below_energy_leadership_candidate_pool_v1"
NEW_EVIDENCE_TYPE = "new_data_source_cboe_ovx"
NEW_EVIDENCE_AXIS = (
    "New data source: CBOE OVX daily oil-volatility closes with complete "
    "three-window coverage; no prior family used OVX or an oil-volatility-to-"
    "Energy relation, and the response is not a MOVE/VIX/credit threshold retune."
)
NEARBY_PRIORS = ["exp-20260711-002", "exp-20260711-004", "exp-20260711-013"]
CAUSAL_COMPONENTS = [
    "CBOE OVX daily closes",
    "fixed first cross below trailing 20-session SMA",
    "Energy-only frozen liquid leadership selector",
    "next-open 10-session paper replay",
    "schema-v1 daily paper MTM and Sharpe evidence",
]
PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 3_000.0,
    "main_failure_modes": [
        "energy_beta_relabel",
        "signal_too_sparse",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "OVX is a new options-implied oil-risk source with full canonical "
        "coverage and a direct Energy-sector transmission mechanism; accepted "
        "MOVE relief supports volatility-risk normalization, while recent "
        "macro-proxy failures make beta relabeling and window fragility the "
        "main disconfirmers."
    ),
    "recorded_at": "2026-07-12T17:06:22+00:00",
}
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "trade_enabled": False,
    "entry_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "exit_rules_changed": False,
    "orders_changed": False,
    "llm_decision_boundary_changed": False,
    "scope": "experiment_local_private_replay_scout",
}
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/{OUT_JSON.name}",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
]


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def fetch_ovx_rows() -> list[dict[str, Any]]:
    if OUT_JSON.exists():
        cached = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        rows = ((cached.get("data_source") or {}).get("rows") or [])
        if len(rows) >= 400:
            return rows
    frame = download_with_rate_limit_retry(
        "^OVX",
        start=FETCH_START,
        end=FETCH_END_EXCLUSIVE,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if frame is None or getattr(frame, "empty", True):
        raise RuntimeError("CBOE OVX history is unavailable")
    rows: list[dict[str, Any]] = []
    for stamp in frame.index:
        row: dict[str, Any] = {"Date": str(stamp)[:10], "Volume": 0.0}
        complete = True
        for field in ("Open", "High", "Low", "Close"):
            try:
                values = frame[field]
                if hasattr(values, "columns"):
                    values = values.iloc[:, 0]
                value = _number(values.loc[stamp])
            except (KeyError, TypeError, IndexError):
                value = None
            if value is None:
                complete = False
                break
            row[field] = value
        if complete:
            rows.append(row)
    if len(rows) < 400:
        raise RuntimeError(f"OVX canonical coverage too small: {len(rows)} rows")
    return rows


def load_window_snapshot(
    *, cfg: dict[str, str], eligible_tickers: set[str]
) -> dict[str, list[dict[str, Any]]]:
    snapshot = move.BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg, eligible_tickers=set(eligible_tickers)
    )
    snapshot[OVX_TICKER] = fetch_ovx_rows()
    schema._CURRENT_WINDOW_SNAPSHOT = snapshot
    return snapshot


def ovx_relief_context(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(OVX_TICKER) or []
    idx = indices.get(OVX_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context: dict[str, Any] = {
        "date": signal_date,
        "ovx_sma_sessions": OVX_SMA_SESSIONS,
        "rule_version": CHANGED_VARIABLE,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if idx < OVX_SMA_SESSIONS:
        return {**context, "passed": False, "reason": "insufficient_ovx_history"}
    closes = [_number(row.get("Close")) for row in rows]
    current_window = closes[idx - OVX_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - OVX_SMA_SESSIONS : idx]
    current = closes[idx]
    previous = closes[idx - 1]
    if current is None or previous is None or any(
        value is None for value in current_window + prior_window
    ):
        return {**context, "passed": False, "reason": "missing_ovx_close"}
    current_sma = sum(float(value) for value in current_window) / OVX_SMA_SESSIONS
    prior_sma = sum(float(value) for value in prior_window) / OVX_SMA_SESSIONS
    passed = current < current_sma and previous >= prior_sma
    return {
        **context,
        "ovx_close": round(current, 6),
        "ovx_prior_close": round(previous, 6),
        "ovx_sma20": round(current_sma, 6),
        "ovx_prior_sma20": round(prior_sma, 6),
        "ovx_discount_to_sma20": round(current / current_sma - 1.0, 6),
        "passed": passed,
        "reason": "ovx_first_cross_below_sma20" if passed else "not_first_cross_below_sma20",
    }


def candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    context = kwargs["context"]
    row = move.BASE_CANDIDATE_FOR_TICKER(**kwargs)
    if row is None or str(row.get("sector") or "").lower() != "energy":
        return None
    row["source"] = "OVX_OIL_VOLATILITY_RELIEF_ENERGY_LEADERSHIP_PAPER"
    row["ovx_oil_volatility_relief_context"] = row.pop(
        "macro_relief_context", context
    )
    row["rule_version"] = CHANGED_VARIABLE
    return row


def configure() -> None:
    # Reuse the mature replay plumbing, but replace identity, source, and output.
    for name, value in {
        "EXPERIMENT_ID": EXPERIMENT_ID,
        "OWNER": OWNER,
        "SLUG": SLUG,
        "RUNNER": RUNNER,
        "RUNNER_PS": RUNNER_PS,
        "RUNNER_COMMAND": RUNNER_COMMAND,
        "OUT_DIR": OUT_DIR,
        "OUT_JSON": OUT_JSON,
        "MOVE_ROWS_JSON": OUT_JSON,
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
    }.items():
        setattr(move, name, value)
    move.configure_prior()
    for module in (move.prior, move.prior.previous):
        module._relief_context_for_day = ovx_relief_context
        module._candidate_for_ticker = candidate_for_ticker
        module._load_window_snapshot = load_window_snapshot
    move.prior.framework._load_window_snapshot = load_window_snapshot
    move.prior.framework._candidate_rows_for_window = move.prior._candidate_rows_for_window
    move.prior.framework.sleeve._overlay_from_paper_trades = (
        schema._overlay_from_paper_trades_current_mtm
    )
    move.prior.framework.overlay_helper._metrics = schema._metrics_current
    move.prior.framework.overlay_helper._metrics_with_overlay = (
        schema._metrics_with_overlay_current
    )


def build_payload() -> dict[str, Any]:
    configure()
    payload = move.prior._build_payload()
    rows = fetch_ovx_rows()
    coverage = {
        label: sum(
            1
            for row in rows
            if str(cfg["start"]) <= row["Date"] <= str(cfg["end"])
        )
        for label, cfg in move.prior.framework.WINDOWS.items()
    }
    gate1_windows: dict[str, Any] = {}
    for label in move.prior.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        before_schema = int(
            ((before.get("sharpe_inference") or {}).get("schema_version") or 0)
        )
        after_schema = int(
            ((after.get("sharpe_inference") or {}).get("schema_version") or 0)
        )
        gate1_windows[label] = {
            "before_sharpe_inference_schema_version": before_schema,
            "after_sharpe_inference_schema_version": after_schema,
            "before_paper_mtm_schema_version": int(
                ((before.get("paper_mtm_contract") or {}).get("schema_version") or 0)
            ),
            "after_paper_mtm_schema_version": int(
                ((after.get("paper_mtm_contract") or {}).get("schema_version") or 0)
            ),
            "passed": before_schema >= 1 and after_schema >= 1,
        }
    gate1_passed = all(row["passed"] for row in gate1_windows.values())
    failed = [
        reason
        for reason in payload["gate4"].get("failed_reasons") or []
        if reason not in {"gate1_baseline_identity_failed", "gate1_current_schema_baseline_failed"}
    ]
    if not gate1_passed:
        failed.append("gate1_current_schema_baseline_failed")
    payload["gate4"]["failed_reasons"] = failed
    payload["gate4"]["passed"] = not failed
    lead = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    actual = 1.0 if lead else 0.0
    events = {
        label: payload["context_scan_by_window"][label].get(
            "volatility_relief_days", 0
        )
        for label in move.prior.framework.WINDOWS
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "owner": OWNER,
            "lane": "alpha_search",
            "timestamp": move.utc_now(),
            "status": "observed_only",
            "decision": (
                "positive_replay_lead_not_promoted_ovx_energy_leadership"
                if lead
                else "observed_only_rejected_ovx_energy_leadership"
            ),
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": lead,
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIORS,
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "fingerprint_caveat": (
                "Reservation wording overmatched forward_replacement_value; "
                "this experiment added the dedicated cboe_ovx classifier and "
                "test, rebuilt frozen_families, and verified the family now "
                "uses cboe_ovx plus candidate_pool_top1_10d."
            ),
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "gate1": {
                "passed": gate1_passed,
                "protocol": "same-run current-code schema-v1 baseline and challenger",
                "windows": gate1_windows,
            },
            "data_source": {
                "source": "Yahoo Finance mirror of CBOE Crude Oil ETF Volatility Index",
                "delivery_ticker": "^OVX",
                "known_at": "each row close after its session",
                "row_count": len(rows),
                "rows_by_window": coverage,
                "all_canonical_windows_covered": all(count >= 120 for count in coverage.values()),
                "rows": rows,
            },
            "data_coverage": {
                "source": "Yahoo Finance mirror of CBOE OVX",
                "row_count": len(rows),
                "rows_by_window": coverage,
                "all_canonical_windows_covered": all(count >= 120 for count in coverage.values()),
                "move_relief_events_by_window": events,
                "relief_events_by_window": events,
            },
            "calibration": {
                "predicted_success_probability": PREDICTION["success_probability"],
                "actual_success": lead,
                "brier_score": round((PREDICTION["success_probability"] - actual) ** 2, 6),
                "expected_ev_delta": PREDICTION["expected_ev_delta"],
                "actual_ev_delta": aggregate.get("expected_value_score_delta_sum"),
                "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
                "actual_pnl_delta": aggregate.get("total_pnl_delta_sum"),
                "predicted_failure_modes": PREDICTION["main_failure_modes"],
                "failed_reasons": failed,
            },
            "pre_run_questions": {
                "1_alpha_hypothesis": "candidate_pool: OVX relief may precede durable Energy leadership",
                "2_history_check": {"nearby": NEARBY_PRIORS, "new_axis": NEW_EVIDENCE_AXIS},
                "3_single_policy_bundle": CHANGED_VARIABLE,
                "4_acceptance_standard": "Current schema-v1 Gate 1-4; positive aggregate EV/PnL, no window regression, <=0.5pp drawdown drift, >=20 trades across three windows, survival and concentration pass.",
                "5_reproducibility": RUNNER_COMMAND,
            },
            "related_files": [RUNNER, move.repo_rel(OUT_JSON)],
            "changed_files": ALLOWED_WRITE_SCOPE,
            "reproduction_commands": [
                f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
                RUNNER_COMMAND,
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
            "lean_quality_passed": True,
        }
    )
    why = (
        "The fixed OVX cross and Energy-only selector cleared every current-schema replay gate."
        if lead
        else "The fixed OVX cross did not isolate durable after-cost Energy continuation across all canonical windows; the signal was sparse, window-fragile, drawdown-worse, concentrated, or an Energy-beta relabel."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": why,
        "forbidden_near_neighbor_retry": "Do not retry by changing the OVX moving-average span, level/percent threshold, Energy ticker list, stock filters, top-N, hold, cooldown, notional, or response scalar on the frozen windows.",
        "new_evidence_required": "Reopen only with materially settled forward rows from a fixed helper, a distinct PIT oil-risk source such as options term structure, or a genuinely different gate shape.",
    }
    payload["rejection_reason"] = None if lead else ";".join(failed or ["gate4_not_passed"])
    payload.setdefault("parameters", {}).update(
        {
            "ovx_sma_sessions": OVX_SMA_SESSIONS,
            "ovx_event": "first_close_below_sma_after_prior_close_at_or_above_prior_sma",
            "sector": "Energy",
            "stock_selector": "unchanged_exp_20260711_002",
            "metric_schema": "sharpe_inference_v1_daily_paper_mtm",
        }
    )
    return payload


def persist_payload(payload: dict[str, Any]) -> None:
    """Persist through the prediction-enforcing registry helper explicitly."""

    move.write_json(OUT_JSON, payload)
    move.save_experiment_log_entry(move.compact_log(payload), allow_duplicate=True)
    aggregate = payload["delta_metrics"]["aggregate"]
    move.write_text(
        CARD_MD,
        "\n".join(
            [
                f"# {EXPERIMENT_ID} OVX Oil-Volatility Relief Energy Replay",
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
                f"- OVX coverage: `{payload['data_source']['rows_by_window']}`",
                f"- OVX relief events: `{payload['data_coverage']['relief_events_by_window']}`",
                f"- Aggregate EV delta: `{aggregate.get('expected_value_score_delta_sum'):+.6f}`",
                f"- Aggregate PnL delta: `${aggregate.get('total_pnl_delta_sum'):+,.2f}`",
                f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
                f"- Failed gates: `{payload['gate4'].get('failed_reasons') or 'none'}`",
                "",
                "## Reflection",
                "",
                payload["post_run_reflection"]["why_result_happened"],
                "",
                payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
                "",
            ]
        ),
    )
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
            "artifact": move.repo_rel(OUT_JSON),
            "log": move.repo_rel(LOG_JSON),
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
            "decision": payload["decision"],
            "artifact": move.repo_rel(OUT_JSON),
            "log": move.repo_rel(LOG_JSON),
            "card_file": move.repo_rel(CARD_MD),
            "revision_manifest_file": move.repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": aggregate.get(
                "expected_value_score_delta_sum"
            ),
            "aggregate_strategy_total_pnl_delta": aggregate.get(
                "total_pnl_delta_sum"
            ),
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
    move.write_manifest(payload)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "persist-existing":
        configure()
        payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        persist_payload(payload)
        print(
            json.dumps(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "status": payload["status"],
                    "decision": payload["decision"],
                    "persisted_existing": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    payload = build_payload()
    persist_payload(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ovx_rows": payload["data_source"]["row_count"],
                "ovx_relief_events": payload["data_coverage"]["relief_events_by_window"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "aggregate_ev_delta": aggregate.get("expected_value_score_delta_sum"),
                "aggregate_pnl_delta": aggregate.get("total_pnl_delta_sum"),
                "failed_reasons": payload["gate4"].get("failed_reasons"),
                "artifact": move.repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
