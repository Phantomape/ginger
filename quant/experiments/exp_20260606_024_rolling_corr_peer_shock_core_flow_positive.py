"""exp-20260606-024: core-flow confirmed peer-shock lag candidates.

Replay-only alpha search. This tests one production-visible candidate-source
variable on top of exp-20260606-018: rolling-correlation peer-shock lag
candidates are admitted only on dates with same-day core A/B entry flow and
only when the laggard candidate itself closed positive on the signal day.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import exp_20260606_018_rolling_corr_peer_shock_lag_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260606-024"
STEM = "rolling_corr_peer_shock_core_flow_positive"
TRIAL_FAMILY = "rolling_corr_peer_shock_core_flow_candidate_pool"
TRIAL_VARIANT_ID = "core_flow_positive_laggard_top1_next_open_10d_v1"
CHANGED_VARIABLE = "rolling_corr_peer_shock_core_flow_positive_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_024_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

CORE_FLOW_CONFIRMATION_REQUIRED = True
MIN_CANDIDATE_SIGNAL_RETURN = 0.0

PREDICTION = {
    "success_probability": 0.23,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "core_flow_overfit",
        "target_sample_too_small",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260606-018 had broad positive aggregate and low concentration "
        "but failed old_thin; preflight attribution shows same-day core-flow "
        "plus positive candidate reaction may remove the old_thin tail while "
        "remaining production-visible and free-OHLCV based."
    ),
    "recorded_at": "2026-06-06T19:23:35+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same core-flow "
        "confirmation, positive candidate signal-day return, rolling 60-day "
        "correlation, peer-shock fields, next-open paper entry, 10-trading-day "
        "exit, costs, cooldown, and concentration controls in both replay and "
        "daily production before any report queue, paper ledger, candidate "
        "priority, sizing, watchlist, or order surface could change."
    ),
}

BASE_CANDIDATE_ROWS_FOR_WINDOW = previous._candidate_rows_for_window
BASE_BUILD_PAYLOAD = previous._build_payload
BASE_BUILD_LOG_RECORD = previous._build_log_record
BASE_GATE4 = previous.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _candidate_rows_for_window(**kwargs: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, peer_contexts, scan = BASE_CANDIDATE_ROWS_FOR_WINDOW(**kwargs)
    raw_count = len(candidates)
    candidates = [row for row in candidates if row.get("same_day_ab_overlap")]
    scan = dict(scan)
    scan.update(
        {
            "core_flow_confirmation_required": CORE_FLOW_CONFIRMATION_REQUIRED,
            "positive_candidate_signal_return_required": True,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "raw_candidates_before_core_flow_filter": raw_count,
            "raw_candidates_after_core_flow_filter": len(candidates),
        }
    )
    return candidates, peer_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_core_flow_peer_shock_lag"
        if gate["passed"]
        else "rejected_core_flow_peer_shock_lag_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Core-flow confirmed rolling-correlation peer-shock candidates "
                "may expand the default-off paper pool only when the same "
                "signal date already has core A/B entry flow and the candidate "
                "itself closes positive."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": (
                "production_visible_core_flow_confirmation_plus_free_ohlcv_relation"
            ),
            "nearby_prior_experiments": [
                "exp-20260606-018",
                "exp-20260606-004",
                "exp-20260606-006",
                "exp-20260606-014",
                "exp-20260606-015",
            ],
            "prior_trial_count": 1,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that core-flow confirmation "
                "only selects dates where the existing core stack is already "
                "risk-on, so the extra peer-lag row may still be redundant or "
                "old-window fragile. A retry would need forward replacement "
                "rows or a true relation source, not another local OHLCV "
                "threshold sweep."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. Live "
                "activation would require closed forward replacement-value "
                "rows and a separate Gate 1-4 trade adapter."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "core_flow_confirmation_required": CORE_FLOW_CONFIRMATION_REQUIRED,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: peer-shock laggards are cleaner when "
            "confirmed by same-day core A/B entry flow and their own positive "
            "signal-day close-to-close return."
        ),
        "2_history_check": {
            "exp-20260606-018": (
                "Rolling-correlation peer-shock lag source improved aggregate "
                "EV/PnL with 337 trades and low concentration, but failed "
                "old_thin and drawdown. This run changes the candidate source "
                "to require core-flow confirmation plus positive candidate "
                "same-day reaction."
            ),
            "broad_OHLCV_recent_winner_family": (
                "exp-20260606-004/006/014/015 failed as broad own-momentum or "
                "breakout relabeling. This run keeps the peer-shock relation "
                "and same-day core-flow confirmation instead of adding noisy "
                "standalone broad winners."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes. A positive replay still "
            "requires shared adapter parity before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_024_rolling_corr_peer_shock_core_flow_positive.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted"
        if payload["gate4"]["passed"]
        else "rejected"
    )
    payload["interpretation"] = (
        "The core-flow confirmed peer-shock lag source cleared Gate 4 as a "
        "replay-only/default-off lead. No production surface was promoted; a "
        "shared adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The core-flow confirmed peer-shock lag source did not clear Gate "
            "4; do not promote or locally retune this peer-lag family on the "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Core-flow raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=scan.get("raw_candidates_after_core_flow_filter", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core-Flow Confirmed Peer-Shock Lag",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = BASE_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "accepted": payload["gate4"]["passed"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "negative_reflection": payload["negative_reflection"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
        }
    )
    return record


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    previous.EXPERIMENT_ID = EXPERIMENT_ID
    previous.STEM = STEM
    previous.TRIAL_FAMILY = TRIAL_FAMILY
    previous.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    previous.CHANGED_VARIABLE = CHANGED_VARIABLE
    previous.RULE_VERSION = RULE_VERSION
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous.MIN_CANDIDATE_SIGNAL_RETURN = MIN_CANDIDATE_SIGNAL_RETURN
    previous.PREDICTION = PREDICTION
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous._candidate_rows_for_window = _candidate_rows_for_window
    previous._gate4 = _gate4
    previous._build_payload = _build_payload
    previous._build_card = _build_card
    previous._build_log_record = _build_log_record
    previous._write_manifest = _write_manifest

    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
