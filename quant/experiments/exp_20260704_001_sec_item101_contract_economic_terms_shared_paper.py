"""exp-20260704-001: SEC Item 1.01 economic-terms shared paper replay.

This runner tests one fixed policy bundle: take the SEC Item 1.01 contract
relation provenance surface, keep only rows whose shared observer extractor
labels them as ``amount_or_duration``, then run the existing default-off
issuer-self paper helper with the unchanged top-1/day, next-open, 10-session
exit, and $4,000 notional contract.

The global historical rows currently predate the exp-20260703-022 economic
field contract, so the runner rebuilds the observer rows in memory from the
same local SEC text files. It does not rewrite the global observer surface.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for path in (REPO_ROOT, QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR, SCRIPTS_DIR):
    path_s = str(path)
    if path_s not in sys.path:
        sys.path.insert(0, path_s)

import exp_20260703_019_sec_item101_contract_relation_shared_paper as base  # noqa: E402
from sec_contract_relation_provenance import (  # noqa: E402
    build_surface_from_paths,
    source_text_glob,
)


EXPERIMENT_ID = "exp-20260704-001"
OWNER = "alpha-explore"
STEM = "sec_item101_contract_economic_terms_shared_paper"
CHANGED_VARIABLE = "sec_item101_contract_economic_terms_shared_default_off_top1_10d_v1"
TRIAL_FAMILY = "sec_item101_contract_economic_terms_shared_default_off"
TRIAL_VARIANT_ID = "shared_amount_or_duration_top1_10d_v1"
MECHANISM_FAMILY = "production_visible_sec_contract_relation_candidate_pool_alpha"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_001_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

PREDICTION = {
    "success_probability": 0.27,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_comparator_not_beaten",
        "window_regression",
        "target_concentration",
        "public_archive_pit_caveat",
    ],
    "confidence_reason": (
        "The exp-20260703-021 fixed amount_or_duration subset separated "
        "cash/SPY/QQQ replacement value and exp-20260703-022 moved the exact "
        "field contract into the shared observer, but exp-20260703-019 rejected "
        "the raw relation helper and SEC text base rates are poor, so the "
        "promotion odds remain low."
    ),
    "recorded_at": "2026-07-04T00:05:09+00:00",
}

SOURCE_ACTIVATION_BOUNDARY = {
    "source": (
        "local SEC Item 1.01 contract-relation provenance rows rebuilt in memory "
        "from shared sec_contract_relation_provenance source_text_glob"
    ),
    "rows_path": "data/non_ohlcv/sec_contract_relation_provenance/rows.jsonl",
    "historical_surface_note": (
        "The checked-in full historical rows were materialized before the "
        "economic_terms_bucket field existed; this runner rebuilds rows in "
        "memory and does not rewrite the observer surface."
    ),
    "pit_boundary": (
        "accepted_at mapped to usable_trade_date from the SEC public archive; "
        "this remains a public-archive PIT proxy, not a live EDGAR timestamp feed."
    ),
    "new_evidence_axis": (
        "new gate shape and implementation boundary: first shared default-off "
        "full-stack test of the fixed exp-20260703-021 amount_or_duration "
        "economic-terms policy after exp-20260703-022 moved that exact field "
        "contract into the daily observer; no regex, priority, top-N, hold, "
        "cooldown, notional, or response-curve change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: SEC 8-K Item 1.01 issuer-self contract rows "
        "with predeclared machine-checkable amount or duration economics may be "
        "promotable to a shared default-off paper candidate source, improving "
        "replacement value versus the rejected raw Item 1.01 helper without "
        "changing regexes, relation priority, top-N, hold, cooldown, notional, "
        "or response curves."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new warned on SEC text near-neighbors and saturated "
            "sec_text_event candidate_pool_top1_10d; override was accepted as "
            "new_gate_shape for the fixed economics full-stack boundary."
        ),
        "exp-20260703-019": (
            "Rejected the raw issuer-self shared helper: aggregate EV/PnL "
            "negative, two windows regressed, and target concentration failed."
        ),
        "exp-20260703-021": (
            "Observed-only positive lead: amount_or_duration rows had positive "
            "cash/SPY/QQQ replacement value and positive lift versus controls."
        ),
        "exp-20260703-022": (
            "Accepted measurement repair that moved the economics extractor into "
            "the shared observer field contract for future daily rows."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md canonical windows with the existing shared paper "
        "helper fed only fixed amount_or_duration rows: positive aggregate EV/PnL, "
        "no EV/PnL window regression, >=2 EV-improved target windows, >=20 target "
        "trades, drawdown drift <=0.5pp, survival >=5%, concentration guards, "
        "accepted compression/distribution comparators beaten, and full-stack "
        "daily/parity contract recorded."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260704_001_sec_item101_contract_economic_terms_shared_paper.py"
    ),
}


def _economic_relation_rows() -> list[dict]:
    rows, _summary = build_surface_from_paths(source_text_glob())
    filtered = [
        row
        for row in rows
        if row.get("relation_quality") == "specific_relation_phrase"
        and row.get("economic_terms_bucket") == "amount_or_duration"
    ]
    return filtered


def _patch_base() -> None:
    base.__file__ = __file__
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.OWNER = OWNER
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.MECHANISM_FAMILY = MECHANISM_FAMILY
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.PREDICTION = PREDICTION
    base.SOURCE_ACTIVATION_BOUNDARY = SOURCE_ACTIVATION_BOUNDARY
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_sec_item101_contract_relation_rows = _economic_relation_rows


def main() -> int:
    _patch_base()
    payload = base.build_payload()
    payload["experiment_id"] = EXPERIMENT_ID
    payload["hypothesis"] = PRE_RUN_QUESTIONS["1_alpha_hypothesis"]
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["single_causal_variable"] = CHANGED_VARIABLE
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["mechanism_family"] = MECHANISM_FAMILY
    payload["new_evidence_type"] = "new_gate_shape_shared_default_off_promotion"
    payload["parameters"]["economic_terms_bucket_required"] = "amount_or_duration"
    payload["parameters"]["policy_changes_from_exp_20260703_019"] = (
        "Keep only rows with economic_terms_bucket=amount_or_duration; all "
        "relation priority, top-1, notional, hold, cost, and execution semantics "
        "unchanged."
    )
    payload["gate2"]["runtime_fields"].extend(
        [
            "economic_terms_bucket",
            "contract_amount_count",
            "contract_duration_count",
            "normalized_counterparty_count",
        ]
    )
    payload["gate2"]["historical_surface_note"] = SOURCE_ACTIVATION_BOUNDARY[
        "historical_surface_note"
    ]
    payload["production_impact"]["parity_note"] = (
        "The existing shared helper is reused for replay and snapshot semantics "
        "after feeding it the fixed amount_or_duration observer rows. No live "
        "orders are emitted and trade_enabled remains false."
    )
    if payload["accepted"]:
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "The fixed amount_or_duration subset survived the shared-helper "
                "promotion and beat the accepted paper comparators across the "
                "canonical windows while leaving live/default behavior off."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep Item 1.01 amount regexes, duration regexes, "
                "counterparty-count thresholds, relation priority, top-N, hold, "
                "cooldown, notional, source priority, or response curves on the "
                "same frozen windows."
            ),
            "new_evidence_required": (
                "Forward daily rows with closed replacement value, true EDGAR "
                "timestamp PIT repair, exhibit-level normalized counterparty "
                "identity, contract revenue exposure, or a different non-SEC-text "
                "economic relation source."
            ),
        }
    else:
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "The fixed amount_or_duration Item 1.01 policy failed the "
                "predeclared full-stack Gate 4: "
                + ("; ".join(payload["gate4"]["failed_reasons"]) or "none")
            ),
            "forbidden_near_neighbor_retry": (
                "Do not sweep Item 1.01 amount regexes, duration regexes, "
                "counterparty-count thresholds, relation priority, top-N, hold, "
                "cooldown, notional, source priority, or response curves on the "
                "same SEC public-archive sample."
            ),
            "new_evidence_required": (
                "Materially more closed forward rows, a real PIT EDGAR timestamp "
                "boundary, exhibit-level normalized customer/supplier identity, "
                "contract revenue exposure, or a different non-SEC-text source."
            ),
        }
    base.persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "aggregate_ev_delta": payload["expected_value_score_delta"],
                "aggregate_pnl_delta": payload["total_pnl_delta"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "by_window_trades": {
                    label: len(trades)
                    for label, trades in payload["target_trades_by_window"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
