"""exp-20260607-001: core-selected anchor peer-lag candidate pool.

Replay-only alpha search. This tests one production-visible free-OHLCV relation
source: use only same-day core-selected A/B entries as positive-shock peer
anchors, then admit correlated liquid laggards for next-open default-off paper
observation.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import exp_20260606_024_rolling_corr_peer_shock_core_flow_positive as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260607-001"
STEM = "core_selected_anchor_peer_lag"
TRIAL_FAMILY = "rolling_corr_core_selected_anchor_peer_lag_candidate_pool"
TRIAL_VARIANT_ID = "core_selected_anchor_peer_lag_top1_next_open_10d_v1"
CHANGED_VARIABLE = "core_selected_anchor_peer_lag_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_001_{STEM}.json"
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

CORE_SELECTED_ANCHOR_REQUIRED = True

PREDICTION = {
    "success_probability": 0.19,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "sample_too_thin",
        "window_regression",
        "anchor_redundant_with_existing_peer_shock",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted peer-shock evidence supports free OHLCV relation alpha, but "
        "forcing the shock anchor to be a core-selected ticker may over-thin "
        "the sample or duplicate existing core flow."
    ),
    "recorded_at": "2026-06-07T00:06:40+00:00",
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
        "require the shared rolling-correlation peer-shock helper to expose "
        "the same core-selected anchor mode in both historical replay and "
        "daily default-off snapshots before any report queue, paper ledger, "
        "candidate priority, sizing, watchlist, or order surface could change."
    ),
}

BASE_CANDIDATE_ROWS_FOR_WINDOW = previous._candidate_rows_for_window
BASE_BUILD_PAYLOAD = previous._build_payload
BASE_BUILD_LOG_RECORD = previous._build_log_record
BASE_GATE4 = previous._gate4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _core_entry_tickers_by_date(before_result: dict[str, Any]) -> dict[str, set[str]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    result: dict[str, set[str]] = {}
    for signal_date, entries in entries_by_date.items():
        tickers = {
            str(entry.get("ticker") or "").upper()
            for entry in entries
            if str(entry.get("ticker") or "").strip()
        }
        result[str(signal_date)] = tickers
    return result


def _candidate_rows_for_window(**kwargs: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, peer_contexts, scan = BASE_CANDIDATE_ROWS_FOR_WINDOW(**kwargs)
    core_tickers_by_date = _core_entry_tickers_by_date(kwargs["before_result"])
    raw_count = len(candidates)
    anchored: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("date") or "")
        peer_ticker = str(row.get("peer_ticker") or "").upper()
        core_tickers = core_tickers_by_date.get(signal_date, set())
        if peer_ticker not in core_tickers:
            continue
        anchored.append(
            {
                **row,
                "core_selected_anchor_required": True,
                "core_selected_anchor_peer_ticker": peer_ticker,
                "core_selected_anchor_ticker_count": len(core_tickers),
                "source_rule_version": RULE_VERSION,
                "rule_version": RULE_VERSION,
            }
        )
    scan = dict(scan)
    scan.update(
        {
            "core_selected_anchor_required": CORE_SELECTED_ANCHOR_REQUIRED,
            "raw_candidates_before_core_selected_anchor_filter": raw_count,
            "raw_candidates_after_core_selected_anchor_filter": len(anchored),
            "days_with_core_selected_anchor_candidates": len(
                {str(row.get("date") or "") for row in anchored}
            ),
        }
    )
    context_by_date = {str(row.get("date") or ""): row for row in peer_contexts}
    filtered_contexts = [
        {
            **context_by_date[day],
            "core_selected_anchor_candidate_count": sum(
                1 for row in anchored if str(row.get("date") or "") == day
            ),
        }
        for day in sorted({str(row.get("date") or "") for row in anchored})
        if day in context_by_date
    ]
    return anchored, filtered_contexts, scan


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
        "positive_replay_lead_not_promoted_core_selected_anchor_peer_lag"
        if gate["passed"]
        else "rejected_core_selected_anchor_peer_lag_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Core-selected A/B entries that themselves shock higher may be "
                "better peer anchors for a correlated laggard default-off paper "
                "candidate than arbitrary peer shocks."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "production_visible_core_selected_anchor_relation",
            "nearby_prior_experiments": [
                "exp-20260606-018",
                "exp-20260606-024",
                "exp-20260606-025",
                "exp-20260606-026",
                "exp-20260606-028",
            ],
            "prior_trial_count": 1,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the core-selected anchor either over-thinned the "
                "accepted peer-shock relation or simply duplicated existing core "
                "risk-on dates. Do not retry by sweeping local correlation, "
                "shock-return, hold-day, cooldown, or notional thresholds; require "
                "forward replacement rows or a materially new relation source."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs shared helper parity for "
                "core-selected anchor mode before production observation. Live "
                "activation would require closed forward replacement-value rows "
                "and a separate Gate 1-4 trade adapter."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "core_selected_anchor_required": CORE_SELECTED_ANCHOR_REQUIRED,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: if the existing core stack selected a ticker "
            "that also has a peer-shock day, its correlated laggards may have "
            "cleaner replacement value than laggards anchored on arbitrary "
            "same-day peer shocks."
        ),
        "2_history_check": {
            "exp-20260606-018": (
                "Any peer-shock lag improved aggregate EV/PnL but failed old_thin "
                "and drawdown."
            ),
            "exp-20260606-024_to_026": (
                "Core-flow plus positive-candidate peer shock passed Gate 4 and "
                "was promoted into a shared default-off helper and daily forward "
                "observation."
            ),
            "exp-20260606-028": (
                "Adding accepted peer shock into lagged consensus was redundant "
                "versus the accepted comparator."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target sample "
            ">=20 across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
            "and concentration guard passes. A positive replay still requires "
            "shared helper parity before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260607_001_core_selected_anchor_peer_lag.py"
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
        "The core-selected anchor peer-lag source cleared Gate 4 as a replay-only "
        "lead. It is not retained as accepted alpha until shared helper parity "
        "and daily default-off exposure are implemented."
        if payload["gate4"]["passed"]
        else (
            "The core-selected anchor peer-lag source did not clear Gate 4; do "
            "not promote or locally retune this peer-lag family on the frozen "
            "windows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Anchor raw | Trades |",
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
                raw=scan.get("raw_candidates_after_core_selected_anchor_filter", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core-Selected Anchor Peer Lag",
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
