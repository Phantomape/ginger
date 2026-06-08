"""exp-20260608-011: revision surprise low-extension tail-state gate.

Replay-only alpha search. This tests one tail-state decision on the prior
revision+surprise-history proxy lead: after the daily top-1 candidate is chosen,
block it when its 20-day return is already more than 35 percentage points above
SPY. No backup candidate is substituted.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260606_016_revision_surprise_history_confirmed as prior


EXPERIMENT_ID = "exp-20260608-011"
STEM = "revision_surprise_low_extension"
TRIAL_FAMILY = "analyst_revision_surprise_low_extension_candidate_pool"
TRIAL_VARIANT_ID = "revision_surprise_selected_top1_low_extension_v1"
CHANGED_VARIABLE = "positive_surprise_history_revision_low_extension_tail_state_v1"
RULE_VERSION = CHANGED_VARIABLE

MAX_RET20_EXCESS_SPY = 0.35

ROOT = prior.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_011_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
REVISION_ROWS_JSON = OUT_DIR / "earnings_revision_rows_summary.json"
REVISION_FILES_JSON = OUT_DIR / "earnings_revision_snapshot_files.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

framework = prior.framework
revision_base = prior.revision_base

_ORIGINAL_CANDIDATE_ROWS = prior._candidate_rows_for_window
_ORIGINAL_BUILD_PAYLOAD = prior._build_payload
_ORIGINAL_ARTIFACT = prior._artifact


def _candidate_rows_for_window(
    frames: dict[str, Any],
    label: str,
    cfg: dict[str, str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected, diagnostics = _ORIGINAL_CANDIDATE_ROWS(frames, label, cfg, before_result)
    kept: list[dict[str, Any]] = []
    blocked_examples: list[dict[str, Any]] = []
    reject_counts: Counter[str] = Counter()

    for row in selected:
        ret20_excess = revision_base._float(row.get("ret20_excess_spy"))
        if ret20_excess is None:
            reject_counts["missing_ret20_excess_spy"] += 1
            reason = "missing_ret20_excess_spy"
        elif ret20_excess > MAX_RET20_EXCESS_SPY:
            reject_counts["ret20_excess_spy_above_tail_cap"] += 1
            reason = "ret20_excess_spy_above_tail_cap"
        else:
            updated = dict(row)
            updated["rule_version"] = RULE_VERSION
            updated["low_extension_tail_state_passed"] = True
            updated["max_ret20_excess_spy"] = MAX_RET20_EXCESS_SPY
            updated["tail_state_policy"] = "selected_top1_gate_no_backup_substitution"
            kept.append(updated)
            continue

        if len(blocked_examples) < 25:
            blocked_examples.append(
                {
                    "ticker": row.get("ticker"),
                    "date": row.get("date") or row.get("signal_date"),
                    "window": label,
                    "ret20_excess_spy": row.get("ret20_excess_spy"),
                    "score": row.get("score"),
                    "reject_reason": reason,
                }
            )

    diag = dict(diagnostics)
    diag["low_extension_tail_gate"] = {
        "max_ret20_excess_spy": MAX_RET20_EXCESS_SPY,
        "policy": "gate prior selected daily top-1; no backup candidate substitution",
        "prior_selected_count": len(selected),
        "kept_selected_count": len(kept),
        "blocked_selected_count": len(selected) - len(kept),
        "reject_counts": dict(sorted(reject_counts.items())),
        "blocked_examples": blocked_examples,
    }
    return kept, diag


def _build_payload() -> dict[str, Any]:
    payload = _ORIGINAL_BUILD_PAYLOAD()
    numeric_passed = bool(payload["gate4"].get("numeric_passed"))
    accepted = False
    if numeric_passed:
        decision = "positive_proxy_lead_not_promoted_revision_surprise_low_extension"
        rationale = (
            "Numeric Gate 4 passed, but this remains a replay-only proxy lead: "
            "the historical EPS-estimate and surprise-history source still "
            "requires a shared PIT analyst-revision adapter with production/"
            "backtest parity before promotion."
        )
    else:
        decision = "rejected_revision_surprise_low_extension_tail_state"
        rationale = (
            "Gate 4 failed; blocking overextended selected candidates did not "
            "make the revision+surprise-history proxy lead robust enough for "
            "retention."
        )

    actual_success = 1 if accepted else 0
    ev_delta = payload["aggregate"]["expected_value_score_delta_sum"]
    pnl_delta = payload["aggregate"]["total_pnl_delta_sum"]

    payload["gate4"].update(
        {
            "passed": accepted,
            "numeric_passed": numeric_passed,
            "decision": decision,
            "rationale": rationale,
            "requires_parity_before_promotion": numeric_passed,
            "source_provenance_guard": {
                "promotable_source": False,
                "reason": "historical EPS estimate snapshots are proxy-grade",
            },
        }
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "rejected",
            "decision": decision,
            "accepted": accepted,
            "hypothesis": (
                "Revision+surprise-history candidates that are not already "
                "overextended versus SPY should keep expectation-revision alpha "
                "while reducing old-thin tail risk."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "analyst_revision_expectation_trajectory",
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260604-029",
                "exp-20260605-029",
                "exp-20260606-016",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "tail_state_classifier_on_existing_proxy_lead",
            "interpretation": rationale,
            "rejection_reason": None if numeric_passed else "; ".join(
                payload["gate4"]["failed_gates"]
            ),
            "prediction": {
                "success_probability": 0.24,
                "expected_ev_delta": None,
                "expected_pnl_delta": None,
                "main_failure_modes": [
                    "old_thin_still_negative",
                    "thin_sample",
                    "proxy_grade_source",
                    "tail_not_isolated",
                    "concentration_failed",
                ],
                "confidence_reason": (
                    "exp-20260606-016 was aggregate-positive but failed "
                    "old_thin, drawdown, and concentration guards; its weak "
                    "window losses clustered in very extended momentum names, "
                    "so this tests a distinct tail-state decision rather than "
                    "another revision or DTE threshold."
                ),
                "recorded_at": "2026-06-08T10:08:17+00:00",
                "actual_success": actual_success,
                "actual_ev_delta": ev_delta,
                "actual_pnl_delta": pnl_delta,
                "brier_score": round((0.24 - actual_success) ** 2, 6),
            },
        }
    )
    payload["parameters"].update(
        {
            "single_changed_variable": CHANGED_VARIABLE,
            "source_relation": (
                "Start from exp-20260606-016's selected daily top-1 "
                "revision+positive-surprise-history candidate, then block "
                "only the selected candidate when ret20_excess_spy is above "
                "35 percentage points. No replacement candidate is selected "
                "for that day."
            ),
            "max_ret20_excess_spy": MAX_RET20_EXCESS_SPY,
            "selection_policy": "selected_top1_gate_no_backup_substitution",
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / tail-state risk: expectation-revision candidates "
            "that have already outrun SPY by more than 35 percentage points "
            "over 20 days are more likely crowded gap-chase entries than "
            "clean underreaction."
        ),
        "2_history_check": {
            "exp-20260604-029": (
                "Raw 20d EPS revision velocity was aggregate-positive but "
                "proxy-grade and old_thin regressed."
            ),
            "exp-20260605-029": (
                "Persistent revision underreaction became aggregate negative; "
                "this run does not retune revision persistence."
            ),
            "exp-20260606-016": (
                "Revision+positive-surprise-history improved aggregate EV/PnL "
                "but failed old_thin, drawdown, and concentration guards."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md canonical three windows; numeric pass requires "
            "positive aggregate EV/PnL, no EV/PnL-regressed window, sufficient "
            "sample, drawdown and concentration guards. Promotion remains "
            "blocked without PIT analyst-revision parity."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_011_revision_surprise_low_extension.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["production_impact"].update(
        {
            "replay_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "trade_enabled": False,
            "alters_orders": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_data_fetch_changed": False,
            "requires_shared_adapter_before_promotion": numeric_passed,
            "parity_note": (
                "Replay-only/default-off. This experiment changes no production "
                "path. A positive result would still need a shared PIT "
                "analyst-revision adapter computing the same tail gate in "
                "historical replay and daily production."
            ),
        }
    )
    payload["production_parity"] = {
        "alters_production_orders": False,
        "alters_live_watchlists": False,
        "alters_core_backtester": False,
        "default_enabled": False,
        "replay_only": True,
        "source_provenance_promotable": False,
        "parity_note": (
            "No production/backtest inconsistency is introduced because this "
            "runner does not touch production code or default-off daily output. "
            "Promotion would require a shared adapter and parity tests."
        ),
    }
    payload["negative_reflection"] = (
        "If rejected, overextension was not an isolated explanation for the "
        "revision+surprise-history proxy lead's weak-window tail. Do not sweep "
        "nearby ret20 caps or revision/DTE thresholds without a true PIT "
        "analyst-estimate source or forward default-off replacement rows."
    )
    payload["post_run_reflection"] = {
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping ret20_excess_spy caps, revision velocity, "
            "days-to-earnings, close-location, volume ratio, hold-day, top-N, "
            "cooldown, or paper notional on the frozen proxy windows."
        ),
        "new_evidence_required": (
            "A retry needs materially new PIT analyst-revision evidence, such "
            "as analyst-count trajectory, revision persistence with vendor "
            "provenance, or forward replacement rows."
        ),
        "outcome_interpretation": rationale,
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["related_files"] = [
        framework._repo_rel(Path(__file__)),
        framework._repo_rel(OUT_JSON),
        framework._repo_rel(BEFORE_JSON),
        framework._repo_rel(AFTER_JSON),
        framework._repo_rel(REVISION_ROWS_JSON),
        framework._repo_rel(REVISION_FILES_JSON),
        framework._repo_rel(LOG_JSON),
        framework._repo_rel(ARTIFACT_MD),
        framework._repo_rel(CARD_MD),
        framework._repo_rel(EXPERIMENT_LOG),
    ]
    return payload


def _artifact(payload: dict[str, Any]) -> str:
    text = _ORIGINAL_ARTIFACT(payload).replace(
        "Revision Surprise-History Confirmed Candidate Pool",
        "Revision Surprise Low-Extension Tail-State Candidate Pool",
    )
    gate = payload["parameters"]
    return (
        text
        + "\n## Low-Extension Tail Gate\n\n"
        + f"- max ret20_excess_spy: `{gate['max_ret20_excess_spy']}`\n"
        + f"- selection policy: `{gate['selection_policy']}`\n"
        + "- production parity: replay-only; no production/default path changed.\n"
    )


def _patch_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.BEFORE_JSON = BEFORE_JSON
    prior.AFTER_JSON = AFTER_JSON
    prior.REVISION_ROWS_JSON = REVISION_ROWS_JSON
    prior.REVISION_FILES_JSON = REVISION_FILES_JSON
    prior.LOG_JSON = LOG_JSON
    prior.ARTIFACT_MD = ARTIFACT_MD
    prior.CARD_MD = CARD_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior._candidate_rows_for_window = _candidate_rows_for_window
    prior._build_payload = _build_payload
    prior._artifact = _artifact


def run(output: Path = OUT_JSON) -> dict[str, Any]:
    _patch_prior()
    return prior.run(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_JSON)
    args = parser.parse_args()
    t0 = time.time()
    payload = run(args.output)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "runtime_seconds": round(time.time() - t0, 1),
                "aggregate": payload["aggregate"],
                "gate4": payload["gate4"],
                "target_trade_summary": {
                    key: payload["target_trade_summary"][key]
                    for key in (
                        "total_trade_count",
                        "total_pnl",
                        "by_window_pnl",
                        "max_single_positive_pnl_share",
                        "positive_pnl_hhi",
                    )
                },
                "artifact": framework._repo_rel(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
