"""exp-20260606-001: shared low-deployment ETF cash-substitute adapter.

This alpha-search run promotes the accepted exp-20260605-035 replay semantics
into the shared default-off low-deployment ETF overlay module, then replays the
same three canonical windows through that shared helper. It does not enable
live orders, ranking, sizing, exits, watchlists, LLM, or news behavior.

No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260605_035_low_deployment_etf_cash_substitute as base
from low_deployment_etf_overlay import (
    replay_low_deployment_etf_cash_substitute_trades,
)


EXPERIMENT_ID = "exp-20260606-001"
STEM = "low_deployment_etf_cash_substitute_shared_adapter"
TRIAL_FAMILY = "low_deployment_etf_cash_substitute_shared_adapter"
TRIAL_VARIANT_ID = "shared_low_deployment_etf_cash_substitute_adapter_v1"
CHANGED_VARIABLE = "shared_low_deployment_etf_cash_substitute_adapter_v1"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_001_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"exp_20260606_001_{STEM}_aggregate_before.json"
AFTER_JSON = OUT_DIR / f"exp_20260606_001_{STEM}_aggregate_after.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

PREDICTION = {
    "success_probability": 0.65,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "shared_adapter_replay_drift",
        "production_cash_semantics_mismatch",
        "old_thin_regression",
        "positive_pnl_concentration",
        "forward_gate_still_blocked",
    ],
    "confidence_reason": (
        "exp-20260605-035 passed the strict three-window risk-allocation gate; "
        "this run changes only whether the same semantics live in a shared "
        "default-off adapter instead of an experiment-only runner."
    ),
    "recorded_at": "2026-06-06T00:05:14Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_paper_adapter_no_live_orders",
    "shared_policy_changed": True,
    "backtester_adapter_changed": False,
    "run_adapter_changed": True,
    "replay_only": False,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "The shared low_deployment_etf_overlay helper now owns the selected "
        "ETF, next-open paper entry, 10-trading-day close exit, one-open-position "
        "cap, slippage/cost model, and no-live-order boundary. The historical "
        "runner calls the same helper used by daily production snapshots."
    ),
}

EXTRA_SCOPE = [
    "quant/low_deployment_etf_overlay.py",
    "quant/test_low_deployment_etf_overlay.py",
    "quant/report_generator.py",
    "docs/production_backtest_parity.md",
    "docs/alpha-optimization-playbook.md",
    "docs/current_state.md",
    "experiments/artifacts/exp-20260606-001_low_deployment_etf_cash_substitute_shared_adapter.md",
]


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, Path):
        return _repo_rel(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _shared_overlay_trades(
    before_result: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return replay_low_deployment_etf_cash_substitute_trades(
        core_backtest_result=before_result,
        ohlcv_by_ticker=snapshot,
        config={
            "fallback_paper_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "max_active_core_positions": base.MAX_ACTIVE_CORE_POSITIONS,
            "max_overlay_open_positions": base.MAX_OVERLAY_OPEN_POSITIONS,
            "state_sma_days": base.STATE_SMA_DAYS,
            "state_momentum_days": base.STATE_MOMENTUM_DAYS,
            "candidate_tickers": base.OVERLAY_CANDIDATES,
        },
    )


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base._overlay_trades = _shared_overlay_trades


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4_passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "accepted" if gate4_passed else "rejected",
            "decision": (
                "accepted_shared_default_off_low_deployment_etf_cash_substitute_adapter"
                if gate4_passed
                else "rejected_shared_low_deployment_etf_cash_substitute_adapter"
            ),
            "hypothesis": (
                "Low core deployment leaves replacement-value gaps; the accepted "
                "low-deployment ETF cash-substitute replay should reproduce as a "
                "shared default-off paper adapter with next-open entry, "
                "10-trading-day close exit, one open ETF position, and no live orders."
            ),
            "change_type": "shared_default_off_paper_cash_substitute_adapter",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "nearby_prior_experiments": [
                "exp-20260605-035",
                "exp-20260510-007",
                "exp-20260605-028",
            ],
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": "production_shared_adapter_replay_parity",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": (
                "The shared helper reproduced the accepted cash-substitute "
                "three-window edge while keeping the sleeve default-off and "
                "order-disabled."
                if gate4_passed
                else "The shared helper failed to reproduce exp035 cleanly; do not retain it."
            ),
            "next_evidence_needed": (
                "Collect closed forward replacement-value rows under the shared "
                "default-off ledger before any live cash-deployment adapter."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel("quant/low_deployment_etf_overlay.py"),
                _repo_rel("quant/test_low_deployment_etf_overlay.py"),
                _repo_rel("quant/report_generator.py"),
                _repo_rel(OUT_JSON),
                _repo_rel(BEFORE_JSON),
                _repo_rel(AFTER_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel("docs/production_backtest_parity.md"),
                _repo_rel("docs/alpha-optimization-playbook.md"),
                _repo_rel("docs/current_state.md"),
            ],
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "capital allocation / candidate-pool extension: low core deployment "
            "creates replacement-value gaps that a liquid ETF cash substitute can "
            "fill using only free OHLCV, now through shared adapter semantics."
        ),
        "2_history_check": {
            "exp-20260605-035": (
                "Accepted replay lead: aggregate EV +3.0292, PnL +$44,306.91, "
                "19 trades, no regressed windows, but replay-only."
            ),
            "exp-20260510-007": (
                "Older raw low-deployment ETF overlay improved windows but used "
                "same-day open-to-close semantics and had cash-semantics blockers."
            ),
            "exp-20260605-028": (
                "Forward readiness audit found low_deployment_etf closest among "
                "default-off sleeves but still below closed forward sample gates."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same three standard windows. As risk/capital allocation, aggregate "
            "EV delta must exceed 10% of baseline, aggregate PnL must be positive, "
            "no window EV/PnL regression, drawdown drift <=0.5pp, survival >=5%, "
            "target trades span all windows, and concentration passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_001_low_deployment_etf_cash_substitute_shared_adapter.py"
        ),
    }
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4_passed,
        "failure_modes_observed": payload["gate4"]["failed_reasons"],
    }
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    aggregate = payload["gate4"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} Shared Low-Deployment ETF Cash Substitute",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "## Aggregate",
        "",
        f"- EV: `{aggregate['baseline_expected_value_score_sum']} -> "
        f"{aggregate['after_expected_value_score_sum']}` "
        f"({aggregate['expected_value_score_delta_sum']:+.4f})",
        f"- PnL: `${aggregate['baseline_total_pnl_sum']:,.2f} -> "
        f"${aggregate['after_total_pnl_sum']:,.2f}` "
        f"(${aggregate['total_pnl_delta_sum']:+,.2f})",
        f"- Target trades: `{aggregate['target_trade_count_sum']}`",
        f"- Max drawdown delta: `{aggregate['max_drawdown_delta_max']}`",
        "",
        "## Window Deltas",
        "",
        "| Window | EV delta | PnL delta | Trades |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in payload["gate4"]["aggregate"]["target_windows"]:
        metrics = payload["window_metrics"][row]
        lines.append(
            f"| `{row}` | {metrics['delta']['expected_value_score']:+.4f} | "
            f"${metrics['delta']['total_pnl']:+,.2f} | {metrics['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Boundary",
            "",
            "- Shared helper changed: `quant/low_deployment_etf_overlay.py`.",
            "- Daily production remains default-off and `trade_enabled=false`.",
            "- No live/default orders, ranking, sizing, exits, watchlists, LLM, or news path changed.",
            "- No JavaScript was used.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _restore_ticket_scope(payload: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    scope = list(dict.fromkeys([*(ticket.get("allowed_write_scope") or []), *EXTRA_SCOPE]))
    ticket["allowed_write_scope"] = scope
    ticket["nearby_prior_experiments"] = [
        "exp-20260605-035",
        "exp-20260510-007",
        "exp-20260605-028",
    ]
    ticket["status"] = payload["status"]
    ticket["completed_at"] = payload["timestamp"]
    ticket["result"]["artifact_md"] = _repo_rel(ARTIFACT_MD)
    TICKET_JSON.write_text(json.dumps(_safe(ticket), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    _configure_base()
    payload = _patch_payload(base._build_payload())
    base.persist(payload)
    _write_artifact(payload)
    _restore_ticket_scope(payload)
    print(json.dumps(_safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
