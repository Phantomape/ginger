"""exp-20260525-015: SEC special-call state-context notional scout.

Alpha search, replay-only. Tests one deterministic event field on top of the
accepted exp-20260521-013 default-off event adapter: SEC negative-reaction rows
with call/webcast disclosure may deserve extra paper notional only when market
state context is broad_rotation or weak_index.

No JavaScript is used. Live/default orders remain disabled.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_016_event_special_call_flag as parent


EXPERIMENT_ID = "exp-20260525-015"
EXPERIMENT_SLUG = "sec_special_call_state_context_notional"
TRIAL_FAMILY = "sec_special_call_state_context_notional"
CHANGED_VARIABLE = "sec_special_call_state_context_notional_scalar"

REPO_ROOT = parent.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = parent.BASELINE_VARIANT
BASE_SPECIAL_CALL_METADATA = parent._special_call_metadata
TARGET_STATE_BUCKETS = ("broad_rotation", "weak_index")

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-013 event adapter.",
                "special_call_scalar": 1.0,
            },
        ),
        (
            "state_context_call_110",
            {
                "description": "1.10x notional for call/webcast rows in broad/weak states.",
                "special_call_scalar": 1.10,
            },
        ),
        (
            "state_context_call_125",
            {
                "description": "1.25x notional for call/webcast rows in broad/weak states.",
                "special_call_scalar": 1.25,
            },
        ),
    ]
)


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(parent._parent()._safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(parent._parent()._safe(payload), sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _state_context_call_metadata(
    trade: dict[str, Any],
    text_by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metadata = BASE_SPECIAL_CALL_METADATA(trade, text_by_accession)
    raw_special_call_flag = bool(metadata.get("special_call_flag"))
    state_bucket = str(trade.get("state_bucket") or "")
    target_flag = raw_special_call_flag and state_bucket in TARGET_STATE_BUCKETS
    return {
        **metadata,
        "raw_special_call_flag": raw_special_call_flag,
        "state_bucket": state_bucket,
        "target_state_buckets": list(TARGET_STATE_BUCKETS),
        "special_call_state_context_flag": target_flag,
        # parent.build_payload uses this field for scaling and target selection.
        "special_call_flag": target_flag,
    }


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted = bool(payload["gate4"]["passed"])
    decision = (
        "accepted_replay_only_sec_special_call_state_context_notional"
        if accepted
        else "rejected_sec_special_call_state_context_notional"
    )
    selection = dict(payload.get("selection") or {})
    selection["target_field"] = "special_call_state_context_flag"
    selection["target_state_buckets"] = list(TARGET_STATE_BUCKETS)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": decision,
            "decision": decision,
            "lane": "alpha_search",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": payload["best_variant"],
            "change_type": "event_disclosure_quality_allocation_scout",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "mechanism_family": "sec_negative_reaction_event_disclosure_quality",
            "hypothesis": (
                "Prior SEC special-call and operational-specificity scouts had "
                "strong aggregate EV but fragile fixed-window behavior. This tests "
                "whether the same production-visible call/webcast disclosure cue is "
                "stronger when the event occurs in broad_rotation or weak_index "
                "market-state context, without changing event definitions, entries, "
                "exits, source capacity, ranking, core sizing, or live orders."
            ),
            "alpha_hypothesis": {
                "category": "capital allocation / event disclosure-quality scoring",
                "entry_exit_ranking_or_allocation": "capital allocation",
                "playbook_alignment": (
                    "Uses the playbook's SEC disclosure-quality/event-field lane, "
                    "avoids sparse LLM soft-ranking, avoids broad-market and "
                    "state-surface scalar retunes, and does not expand the ticker "
                    "set with low-quality noise."
                ),
            },
            "historical_experiment_check": {
                "exp-20260521-016": (
                    "Binary special_call_flag improved aggregate EV/PnL but failed "
                    "Gate 4 on a small old_thin regression."
                ),
                "exp-20260522-009": (
                    "Operational specificity was directionally strong but failed "
                    "Gate 4/sample-concentration requirements."
                ),
                "exp-20260525-010": (
                    "Reaction-depth special-call notional improved EV but failed "
                    "sample and concentration guards."
                ),
            },
            "nearby_prior_experiments": [
                "exp-20260521-016",
                "exp-20260522-009",
                "exp-20260525-010",
            ],
            "prior_trial_count": 3,
            "new_evidence_type": (
                "production_visible_sec_text_call_disclosure_x_event_state_context_field"
            ),
            "multiple_testing_risk_bucket": "high",
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "Event scoring / capital allocation: call/webcast SEC negative "
                    "reaction rows may be higher replacement value when confirmed by "
                    "broad_rotation or weak_index market-state context."
                ),
                "2_history_check": (
                    "Near-neighbor SEC special-call and operational-specificity "
                    "experiments were positive but not accepted; this changes only "
                    "the state-context qualifier, not the scalar family or event "
                    "source definitions."
                ),
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "docs/backtesting.md three fixed windows; require aggregate "
                    "EV/PnL improvement, zero EV-regressed windows, sample guard, "
                    "risk guard, and replay-only parity before any promotion."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260525_015_sec_special_call_state_context_notional.py"
                ),
            },
            "parameters": {
                "baseline_variant": BASELINE_VARIANT,
                "target_source": parent.TARGET_SOURCE,
                "target_state_buckets": list(TARGET_STATE_BUCKETS),
                "special_call_patterns": list(parent.SPECIAL_CALL_PATTERNS),
                "swept_scalars": [
                    row["special_call_scalar"]
                    for name, row in VARIANTS.items()
                    if name != BASELINE_VARIANT
                ],
                "anti_js": "No JavaScript was used.",
            },
            "selection": selection,
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "default_off_paper_only": True,
                "parity_test_added": False,
                "production_signal_path_changed": False,
                "alters_signal_generation": False,
                "alters_candidate_ranking": False,
                "alters_sizing": False,
                "alters_exits": False,
                "alters_orders": False,
                "live_orders_enabled": False,
                "promotion_requirement": (
                    "If ever accepted, move special_call_state_context_flag into a "
                    "shared event adapter and add parity tests before production "
                    "paper or order behavior changes."
                ),
            },
            "why_not_other_attractive_points": (
                "LLM soft-ranking and expectation-residual leadership remain "
                "coverage-limited. AI optical already has a production-visible "
                "adapter, and recent Space, consumer platform, compute-memory, "
                "broad-market feed, raw ranking, and opening-range lanes have "
                "fresh rejection or anti-repeat evidence. This uses free SEC text "
                "plus existing point-in-time event state context."
            ),
            "next_action": (
                "Do not promote unless Gate 4 passes. If rejected, do not retune "
                "nearby call-disclosure state/scalar variants without new forward "
                "SEC rows or a materially different disclosure-quality field."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(EXPERIMENT_LOG),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    if not accepted:
        payload["rejection_reason"] = (
            f"Best variant `{payload['best_variant']}` failed Gate 4: "
            f"EV improved/regressed windows "
            f"{payload['gate4']['delta']['windows_ev_improved']}/"
            f"{payload['gate4']['delta']['windows_ev_regressed']}, "
            f"sample_guard_passed={payload['gate4']['sample_guard_passed']}, "
            f"risk_guard_passed={payload['gate4']['risk_guard_passed']}."
        )
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["gate4"]
    baseline = payload["before_metrics"][BASELINE_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} SEC Special-Call State-Context Notional",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Alpha search. Tests call/webcast SEC negative-reaction rows only when "
        "`state_bucket` is broad_rotation or weak_index.",
        "",
        "## Gate 4 Result",
        "",
        "| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in parent._parent().base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=baseline[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=baseline[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Sweep",
            "",
            "| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |",
            "|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["delta_metrics"][
        "variant_vs_accepted_event_non_narrow_state_context_adapter"
    ].items():
        lines.append(
            "| {name} | {passed} | {sample} | {risk} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {dd:.4f} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                sample="yes" if row["sample_guard_passed"] else "no",
                risk="yes" if row["risk_guard_passed"] else "no",
                dev=row["aggregate_ev_delta"],
                dpnl=row["aggregate_pnl_delta"],
                improved=row["windows_ev_improved"],
                regressed=row["windows_ev_regressed"],
                dd=row["max_window_drawdown_drift"],
            )
        )
    lines.extend(
        [
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only default-off paper scout. No shared policy, production "
            "adapter, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    original_experiment_id = parent.EXPERIMENT_ID
    original_slug = parent.EXPERIMENT_SLUG
    original_out = parent.OUT_JSON
    original_log = parent.LOG_JSON
    original_ticket = parent.TICKET_JSON
    original_artifact = parent.ARTIFACT_MD
    original_variants = parent.VARIANTS
    original_metadata = parent._special_call_metadata

    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.EXPERIMENT_SLUG = EXPERIMENT_SLUG
    parent.OUT_JSON = OUT_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.VARIANTS = VARIANTS
    parent._special_call_metadata = _state_context_call_metadata
    try:
        payload = _retag_payload(parent.build_payload())
    finally:
        parent.EXPERIMENT_ID = original_experiment_id
        parent.EXPERIMENT_SLUG = original_slug
        parent.OUT_JSON = original_out
        parent.LOG_JSON = original_log
        parent.TICKET_JSON = original_ticket
        parent.ARTIFACT_MD = original_artifact
        parent.VARIANTS = original_variants
        parent._special_call_metadata = original_metadata

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "SEC special-call state-context notional",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    return payload


def main() -> int:
    payload = run()
    print(
        json.dumps(
            parent._parent()._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "ev_delta_vs_baseline": payload["expected_value_score_delta"],
                    "pnl_delta_vs_baseline": payload["total_pnl_delta"],
                    "windows_ev_improved": payload["gate4"]["delta"][
                        "windows_ev_improved"
                    ],
                    "windows_ev_regressed": payload["gate4"]["delta"][
                        "windows_ev_regressed"
                    ],
                    "sample_guard_passed": payload["gate4"]["sample_guard_passed"],
                    "risk_guard_passed": payload["gate4"]["risk_guard_passed"],
                    "max_window_drawdown_drift": payload["gate4"][
                        "max_window_drawdown_drift"
                    ],
                    "out_json": _repo_rel(OUT_JSON),
                    "anti_js": "No JavaScript was used.",
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
