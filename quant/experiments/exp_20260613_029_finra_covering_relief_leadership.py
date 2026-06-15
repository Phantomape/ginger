"""exp-20260613-029: FINRA covering-relief leadership candidate scout.

Replay-only alpha search on a distinct FINRA short-interest mechanism. Prior
accepted FINRA work focused on rising short pressure / borrow pressure. This
run tests the opposite production-visible field: after prior crowding remains
high, a newly published short-interest decline may indicate covering relief and
less supply overhang for an already liquid breakout leader.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260603_006_finra_borrow_pressure_candidate_pool as base


EXPERIMENT_ID = "exp-20260613-029"
STEM = "finra_covering_relief_leadership"
TRIAL_FAMILY = "finra_covering_relief_leadership_candidate_pool"
TRIAL_VARIANT_ID = "dtc_ge_3_short_change_le_minus_5"
CHANGED_VARIABLE = "finra_short_interest_covering_relief_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

MIN_FINRA_DAYS_TO_COVER = 3.0
MAX_FINRA_SHORT_INTEREST_CHANGE_PCT = -5.0

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260613_029_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
FINRA_ROWS_JSON = OUT_DIR / "finra_short_interest_rows.json"
FINRA_FILES_JSON = OUT_DIR / "finra_source_files.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FRAMEWORK = base.FRAMEWORK

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


PREDICTION = {
    "success_probability": 0.20,
    "expected_ev_delta": 0.06,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "covering_already_exhausted_move",
        "biweekly_finra_lag",
        "thin_sample",
        "late_or_old_window_regression",
        "overlap_with_accepted_borrow_pressure",
    ],
    "confidence_reason": (
        "Accepted FINRA/IWM and FINRA/FTD pressure sources prove the free PIT "
        "data is usable, but the covering-relief direction is unvalidated and "
        "may lag price."
    ),
    "recorded_at": "2026-06-13T21:09:21+00:00",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _apply_covering_relief_gate(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()
    rejected_examples: list[dict[str, Any]] = []
    field_examples: list[dict[str, Any]] = []

    for candidate in candidates:
        days_to_cover = _as_float(candidate.get("finra_days_to_cover"))
        short_change_pct = _as_float(candidate.get("finra_short_interest_change_pct"))
        ticker = str(candidate.get("ticker") or "")
        signal_date = str(candidate.get("date") or "")

        if days_to_cover is None:
            reject_counts["missing_finra_days_to_cover"] += 1
            continue
        if short_change_pct is None:
            reject_counts["missing_finra_short_interest_change_pct"] += 1
            continue
        if days_to_cover < MIN_FINRA_DAYS_TO_COVER:
            reject_counts["days_to_cover_below_prior_crowding_threshold"] += 1
            if len(rejected_examples) < 20:
                rejected_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "finra_days_to_cover": days_to_cover,
                        "finra_short_interest_change_pct": short_change_pct,
                        "reason": "days_to_cover_below_prior_crowding_threshold",
                    }
                )
            continue
        if short_change_pct > MAX_FINRA_SHORT_INTEREST_CHANGE_PCT:
            reject_counts["short_interest_decline_not_material"] += 1
            if len(rejected_examples) < 20:
                rejected_examples.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "finra_days_to_cover": days_to_cover,
                        "finra_short_interest_change_pct": short_change_pct,
                        "reason": "short_interest_decline_not_material",
                    }
                )
            continue

        enriched = dict(candidate)
        enriched.update(
            {
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "finra_covering_relief_rule_version": RULE_VERSION,
                "finra_covering_relief_known_at": (
                    "after_signal_date_close_with_latest_published_finra_before_next_open_paper_entry"
                ),
                "finra_covering_relief_trade_enabled": False,
                "finra_covering_relief_alters_orders": False,
                "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
                "max_finra_short_interest_change_pct": (
                    MAX_FINRA_SHORT_INTEREST_CHANGE_PCT
                ),
            }
        )
        filtered.append(enriched)
        if len(field_examples) < 20:
            field_examples.append(
                {
                    "ticker": ticker,
                    "date": signal_date,
                    "finra_days_to_cover": days_to_cover,
                    "finra_short_interest_change_pct": short_change_pct,
                    "candidate_selection_score": candidate.get(
                        "candidate_selection_score"
                    ),
                }
            )

    return filtered, {
        "candidate_count_before_covering_relief_gate": len(candidates),
        "candidate_count": len(filtered),
        "candidate_days": len({row["date"] for row in filtered}),
        "unique_candidate_tickers": len({row["ticker"] for row in filtered}),
        "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
        "max_finra_short_interest_change_pct": MAX_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "covering_relief_reject_counts": dict(sorted(reject_counts.items())),
        "covering_relief_rejected_examples": rejected_examples,
        "covering_relief_field_examples": field_examples,
        "rule_version": RULE_VERSION,
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, audit = base._BASE_CANDIDATE_ROWS_FOR_WINDOW(
        snapshot,
        cfg,
        universe,
        before_result,
    )
    filtered, relief_audit = _apply_covering_relief_gate(candidates)
    enriched_audit = dict(audit)
    enriched_audit.update(relief_audit)
    return filtered, enriched_audit


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = base._BASE_POSTPROCESS_PAYLOAD(payload)
    gate4 = payload["gate4"]
    numeric_gate4_passed = bool(gate4["passed"])
    decision = (
        "positive_replay_lead_not_promoted_finra_covering_relief"
        if numeric_gate4_passed
        else "rejected_finra_covering_relief_leadership"
    )
    status = (
        "observed_only_positive_replay_lead"
        if numeric_gate4_passed
        else "rejected_finra_covering_relief_leadership"
    )
    actual_success = 1 if numeric_gate4_passed else 0
    aggregate = payload["delta_metrics"]["aggregate"]

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": decision,
            "hypothesis": (
                "FINRA published short-interest covering relief after prior "
                "crowding plus existing liquid breakout leadership may identify "
                "cleaner post-overhang continuation candidates than rising "
                "short-pressure squeeze rows."
            ),
            "change_type": "candidate_pool_private_replay_scout",
            "mechanism_family": "finra_short_interest_covering_relief",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": [
                "latest_pit_finra_days_to_cover_ge_3",
                "latest_pit_finra_short_interest_change_pct_le_minus_5",
                "existing_finra_iwm_liquid_breakout_leadership_envelope",
            ],
            "new_evidence_type": "production_visible_official_finra_covering_relief_field",
            "prior_trial_count": 6,
            "nearby_prior_experiments": [
                "exp-20260529-017",
                "exp-20260530-005",
                "exp-20260603-006",
                "exp-20260603-007",
                "exp-20260604-026",
                "exp-20260604-027",
                "exp-20260611-015",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "prediction": {
                **PREDICTION,
                "actual_success": actual_success,
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
                "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "min_finra_days_to_cover": MIN_FINRA_DAYS_TO_COVER,
            "max_finra_short_interest_change_pct": MAX_FINRA_SHORT_INTEREST_CHANGE_PCT,
            "source_definition": [
                *payload["parameters"].get("source_definition", []),
                (
                    "Latest PIT-safe published FINRA row must have days-to-cover "
                    ">= 3.0 and short-interest change pct <= -5.0 before "
                    "admission, while existing FINRA/IWM/liquid-breakout "
                    "leadership envelope remains fixed."
                ),
            ],
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / entry: if a previously crowded breakout leader "
            "shows a newly published material short-interest decline, supply "
            "overhang may have cleared enough for cleaner continuation."
        ),
        "2_history_check": {
            "exp-20260529-017": (
                "Raw FINRA short-pressure breakout was aggregate positive but "
                "failed one-window stability."
            ),
            "exp-20260530-005": (
                "FINRA+IWM confirmation improved all three windows but remained "
                "a replay lead until concentration/freshness issues were handled."
            ),
            "exp-20260603-006/007": (
                "Accepted FINRA borrow-pressure evidence used high days-to-cover "
                "plus positive short-interest change; this run tests the "
                "opposite supply-relief direction, not another threshold retune."
            ),
            "exp-20260604-026/027": (
                "Accepted SEC FTD+FINRA shared adapter validated official "
                "settlement/short-interest data, but recent source arbitration "
                "showed the family should not be expanded by rank tweaks alone."
            ),
            "exp-20260611-015": (
                "Rejected FTD+FINRA allocator-source promotion versus the current "
                "accepted allocator; this run is candidate-pool mechanism scout, "
                "not an allocator-source retry."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Same docs/backtesting.md three windows; aggregate EV/PnL must "
            "improve without material drawdown, survival, trade-count, "
            "concentration, or window-stability deterioration. A positive "
            "private replay remains only a lead until moved into a shared "
            "default-off adapter with run/backtest parity."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260613_029_finra_covering_relief_leadership.py"
        ),
    }
    payload["gate1"] = {
        **payload.get("gate1", {}),
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "protocol_source": "docs/backtesting.md canonical three-window replay",
    }
    payload["gate2"] = {
        **payload.get("gate2", {}),
        "minimum_open_position_fields_checked": ["entry_date", "target_price"],
        "operator_inputs_open_positions_missing_required_fields": 0,
        "covering_relief_required_fields": [
            "finra_days_to_cover",
            "finra_short_interest_change_pct",
            "finra_publication_date",
            "finra_source_url",
        ],
        "llm_dependency": False,
    }
    payload["gate3"] = {
        **payload.get("gate3", {}),
        "core_survival_guard": "baseline min survival remains far above 5%",
        "new_core_filter_added": False,
        "candidate_pool_gate_only": True,
    }
    payload["why_not_other_changes"] = (
        "Skipped LLM soft-ranking because the data remains sparse, skipped "
        "recently failed 13F/Form4/OHLCV relation directions, and did not retune "
        "FINRA score, FTD rank, IWM threshold, cooldown, ranking, sizing, exits, "
        "or concentration guards."
    )
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "default_off_paper_only": True,
        "production_watchlist_changed": False,
        "production_orders_changed": False,
        "trade_enabled": False,
        "promotion_requirement": (
            "A positive replay result is not retained as production behavior "
            "until the identical FINRA covering-relief admission is implemented "
            "in a shared default-off run/backtest adapter with parity tests and "
            "daily snapshot visibility."
        ),
    }
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "parity_note": (
            "This experiment changes no production path, so it cannot introduce "
            "new production/backtest inconsistency. Positive evidence would be "
            "classified only as a replay lead until shared default-off parity is "
            "built."
        ),
    }
    if numeric_gate4_passed:
        interpretation = (
            "FINRA covering relief cleared the numeric three-window replay screen "
            "but remains a positive replay lead, not accepted alpha, because no "
            "shared default-off adapter or daily parity surface was promoted in "
            "this scout."
        )
        negative_reflection = None
    else:
        interpretation = (
            "FINRA covering relief did not clear the three-window promotion "
            "screen. The likely reason is that biweekly short-interest declines "
            "arrive after much of the covering move is already priced, while the "
            "accepted rising-pressure family better captures still-unresolved "
            "demand/supply imbalance."
        )
        negative_reflection = (
            "Do not retry nearby FINRA relief thresholds on the same frozen "
            "windows. A better retry would need borrow fee, borrow availability, "
            "float-normalized short interest, or forward replacement rows that "
            "show the relief signal is not stale."
        )
    payload["interpretation"] = interpretation
    payload["rejection_reason"] = (
        None if numeric_gate4_passed else "; ".join(gate4["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "negative_reflection": negative_reflection,
        "forbidden_near_neighbor_retry": (
            "Do not retry FINRA covering-relief threshold-only variants, and do "
            "not retry FTD/FINRA rank or allocator-source arbitration without "
            "a new borrow-cost, borrow-availability, or forward replacement "
            "dataset."
        ),
        "nearby_retries_forbidden": [
            "finra_covering_relief_threshold_only_retune",
            "ftd_finra_rank_or_source_arbitration_retry_without_new_borrow_data",
        ],
        "new_evidence_required": (
            "Forward replacement rows or a materially richer borrow dataset are "
            "required: borrow fee, lendable-share availability, or "
            "float-normalized short-interest decline with the FINRA publication "
            "lag explicitly modeled."
        ),
        "next_evidence_needed": [
            "forward replacement rows",
            "borrow fee or lendable-share availability",
            "float-normalized short-interest decline with publication lag modeled",
        ],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(BEFORE_AGG_JSON),
        _repo_rel(AFTER_AGG_JSON),
        _repo_rel(FINRA_ROWS_JSON),
        _repo_rel(FINRA_FILES_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOC_TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Candidates before | Relief rejects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in FRAMEWORK.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rejects = sum(audit.get("covering_relief_reject_counts", {}).values())
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} | {rejects} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=audit.get("candidate_count_before_covering_relief_gate", 0),
                rejects=rejects,
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            "# exp-20260613-029 FINRA Covering-Relief Leadership",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: require latest published FINRA days-to-cover "
                ">= 3.0 and short-interest change pct <= -5.0 before admitting "
                "the existing FINRA/IWM/liquid-breakout replay candidate."
            ),
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only scout. No shared policy, run adapter, backtester "
                "adapter, production watchlist, order path, core entry, ranking, "
                "sizing, exits, LLM, or news behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": bool(payload["gate4"]["passed"]),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        Path(__file__),
        OUT_JSON,
        BEFORE_AGG_JSON,
        AFTER_AGG_JSON,
        FINRA_ROWS_JSON,
        FINRA_FILES_JSON,
        LOG_JSON,
        TICKET_JSON,
        DOC_TICKET_JSON,
        CARD_MD,
        ARTIFACT_MD,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": _utc_now(),
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths]
        + [_repo_rel(MANIFEST_JSON)],
        "file_hashes": {
            _repo_rel(path): digest
            for path in paths
            if (digest := _sha256(path)) is not None
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _closeout_registry_and_manifest() -> dict[str, Any]:
    with OUT_JSON.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    _update_ticket_and_registry(payload)
    _write_manifest(payload)
    return payload


def _install() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    base.AFTER_AGG_JSON = AFTER_AGG_JSON
    base.FINRA_ROWS_JSON = FINRA_ROWS_JSON
    base.FINRA_FILES_JSON = FINRA_FILES_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.DOC_TICKET_JSON = DOC_TICKET_JSON
    base.CARD_MD = CARD_MD
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._postprocess_payload = _postprocess_payload
    base._build_report = _build_report


def main() -> int:
    _install()
    exit_code = base.main()
    if exit_code == 0:
        _closeout_registry_and_manifest()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
