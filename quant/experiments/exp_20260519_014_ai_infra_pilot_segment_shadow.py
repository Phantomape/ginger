"""exp-20260519-014: AI infra pilot segment candidate-pool shadow.

Alpha-search follow-up to exp-20260519-011.  The broad history-covered
governed expansion and the current AI_INFRA_AGGRESSIVE pilot subset were both
positive on aggregate EV but failed the three-window gate because the gains
were unstable.  This experiment tests one narrower production-visible causal
family: which current AI infra pilot segment bundle, if any, can be added to
the current core trend/breakout replay without changing the rest of the stack.

The experiment remains replay-only.  It does not change shared policy, the
production universe, risk sizing, ranking, exits, LLM/news, or live orders.

No JavaScript is used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260519_011_core_expansion_all_market_shadow as prior


EXPERIMENT_ID = "exp-20260519-014"
STEM = "exp_20260519_014_ai_infra_pilot_segment_shadow"

REPO_ROOT = prior.base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
DOC_LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
DOC_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_ARTIFACT = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_ai_infra_pilot_segment_shadow.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS: dict[str, list[str]] = {
    "pilot_compute_connectivity": ["INTC", "LITE"],
    "pilot_power_excluded": ["APLD", "INTC", "LITE"],
    "pilot_optical_only": ["LITE"],
    "pilot_compute_only": ["INTC"],
    "pilot_power_only": ["APLD", "BE"],
    "pilot_no_be": ["APLD", "INTC", "LITE"],
    "pilot_no_lite": ["APLD", "BE", "INTC"],
}


def _safe(value: Any) -> Any:
    return prior._safe(value)


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(line)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(compact)
                    replaced = True
                continue
            rows.append(line)
    if not replaced:
        rows.append(compact)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _variant_summary(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "variant": row["variant"],
            "added": row["added"],
            "passed": row["passed"],
            "expected_value_score_delta": row["expected_value_score_delta"],
            "total_pnl_delta": row["total_pnl_delta"],
            "improved_windows": row["gate4"]["improved_windows"],
            "regressed_windows": row["gate4"]["regressed_windows"],
            "candidate_trade_count": row["gate4"]["candidate_trade_count"],
            "candidate_window_count": row["gate4"]["candidate_window_count"],
            "max_drawdown_worse": row["gate4"]["max_drawdown_worse"],
            "survival_rate_min_after": row["gate4"]["survival_rate_min_after"],
        }
        for row in variants
    ]


def _select_variant(variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not variants:
        return None
    return max(
        variants,
        key=lambda row: (
            1 if row["passed"] else 0,
            row["expected_value_score_delta"],
            row["total_pnl_delta"],
            -len(row["gate4"]["regressed_windows"]),
            row["gate4"]["candidate_trade_count"],
        ),
    )


def _markdown(payload: dict[str, Any]) -> str:
    rows = [
        "| Variant | Gate | Added | dEV | dPnL | Improved | Regressed | Candidate trades | Windows | Max DD worse |",
        "|---|:---:|---|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["variant_summary"]:
        rows.append(
            "| {variant} | {gate} | {added} | {ev:+.4f} | ${pnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | {dd:+.4f} |".format(
                variant=row["variant"],
                gate="PASS" if row["passed"] else "FAIL",
                added=", ".join(row["added"]),
                ev=float(row["expected_value_score_delta"] or 0.0),
                pnl=float(row["total_pnl_delta"] or 0.0),
                improved=", ".join(row["improved_windows"]) or "-",
                regressed=", ".join(row["regressed_windows"]) or "-",
                trades=row["candidate_trade_count"],
                windows=row["candidate_window_count"],
                dd=float(row["max_drawdown_worse"] or 0.0),
            )
        )
    selected = payload.get("selected_variant") or {}
    selected_gate = selected.get("gate4") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} AI Infra Pilot Segment Shadow",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single causal variable family: AI_INFRA_AGGRESSIVE pilot candidate-pool segment membership. Signal rules, ranking, sizing, exits, heat, slots, LLM/news, and live orders stay locked.",
            "",
            "## Gate 1 Baseline Note",
            "",
            f"- baseline_alignment_passed: `{payload['gate1']['passed']}`",
            "- reason: non-core AI infra candidates require the cached augmented OHLCV snapshot from `exp-20260501-008`; that augmented baseline drifts from the accepted canonical `exp-20260517-009` core metrics.",
            "- consequence: this is replay-only scout evidence, not acceptance evidence for core promotion.",
            "",
            "## Variant Scout",
            "",
            *rows,
            "",
            "## Selected Variant",
            "",
            f"- selected: `{selected.get('variant')}`",
            f"- gate_passed: `{selected_gate.get('passed')}`",
            f"- EV delta: `{payload.get('expected_value_score_delta')}`",
            f"- PnL delta: `${payload.get('total_pnl_delta')}`",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(_safe(payload["production_impact_closeout"]), indent=2, sort_keys=True),
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_payload() -> dict[str, Any]:
    gate2 = prior.base._audit_open_positions()
    core_universe = set(prior.base.get_universe())

    original_sector_map = dict(prior.risk_engine.SECTOR_MAP)
    prior.risk_engine.SECTOR_MAP.update(prior.CANDIDATE_SECTOR_MAP)
    try:
        baseline_runs = {
            label: prior._run_window(label, sorted(core_universe))
            for label in prior.WINDOWS
        }
        before_metrics = {label: baseline_runs[label]["metrics"] for label in prior.WINDOWS}
        baseline_alignment = prior._baseline_alignment(before_metrics)
        variants = [
            prior._variant_payload(name, sorted(set(added)), baseline_runs)
            for name, added in VARIANTS.items()
        ]
    finally:
        prior.risk_engine.SECTOR_MAP.clear()
        prior.risk_engine.SECTOR_MAP.update(original_sector_map)

    accepted = [row for row in variants if row["passed"]]
    selected = _select_variant(variants)
    selected_summary = selected or {
        "variant": None,
        "after_metrics": None,
        "delta_metrics": None,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "gate4": {"passed": False},
    }
    decision = (
        "promising_ai_infra_pilot_segment_candidate_found"
        if accepted
        else "rejected_ai_infra_pilot_segment_shadow"
    )
    interpretation = (
        "At least one current AI infra pilot segment bundle cleared the three-window candidate-pool shadow gate. Treat it as a default-off paper/universe-governance lead only."
        if accepted
        else (
            "No current AI infra pilot segment bundle cleared the three-window candidate-pool shadow gate. "
            "Aggregate EV was positive in several variants, but every broad enough variant either regressed a window, "
            "worsened max drawdown beyond the guardrail, or had a thin one-window sample."
        )
    )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00",
            "Z",
        ),
        "lane": "alpha_search",
        "status": "observed_only" if accepted else "rejected",
        "decision": decision,
        "hypothesis": (
            "The current AI_INFRA_AGGRESSIVE pilot pool contains distinct production-visible "
            "segments. Segmenting the history-covered pilot candidates may preserve the positive "
            "replacement-value clue from exp-20260519-011 while avoiding old-window or mid-window "
            "regression from weaker segments."
        ),
        "change_type": "candidate_pool_shadow",
        "changed_variable": "ai_infra_pilot_segment_candidate_pool_membership",
        "single_causal_variable": (
            "AI_INFRA_AGGRESSIVE pilot candidate-pool segment membership from production universe registry fields"
        ),
        "parameters": {
            "source_experiment_id": "exp-20260519-011",
            "baseline_experiment_id": prior.CORE_BASELINE_EXPERIMENT_ID,
            "candidate_sector_map": prior.CANDIDATE_SECTOR_MAP,
            "tested_variants": VARIANTS,
            "locked_variables": [
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk enrichment",
                "position sizing",
                "all sizing multipliers",
                "stops and targets",
                "portfolio heat",
                "slot limits",
                "LLM/news replay",
                "event sleeves",
                "pilot sleeve live behavior",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "min_ev_improved_windows": prior.MIN_EV_IMPROVED_WINDOWS,
                "max_ev_regressed_windows": 0,
                "max_drawdown_worse": prior.MAX_DRAWDOWN_WORSE_GUARDRAIL,
                "min_trade_count_sum": prior.MIN_TRADE_COUNT_SUM,
                "min_candidate_trade_count": prior.MIN_CANDIDATE_TRADE_COUNT,
                "min_candidate_window_count": prior.MIN_CANDIDATE_WINDOW_COUNT,
                "min_survival_rate": 0.05,
            },
            "anti_js": "No JavaScript was used.",
        },
        "historical_experiment_check": {
            "nearby_prior_results": {
                "exp-20260501-015": "INTC/LITE clean optical/storage subset was previously unstable on an older stack.",
                "exp-20260519-011": "Broad history-covered governed and current-pilot variants were positive on aggregate but failed due old/mid-window regression and drawdown.",
            },
            "why_this_is_not_duplicate": (
                "This follow-up keeps the latest accepted core stack and tests only "
                "production-visible current AI infra pilot segment membership, not "
                "arbitrary ticker additions or broad all-market expansion."
            ),
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "candidate_pool: a narrower current AI infra pilot segment bundle "
                "may be a better default-off replacement-value surface than broad pilot admission"
            ),
            "2_history_check": (
                "Broad and current-pilot expansion in exp-20260519-011 failed; older INTC/LITE work was unstable. "
                "This run tests segment bundles on the latest accepted core baseline."
            ),
            "3_single_causal_variable": "ai_infra_pilot_segment_candidate_pool_membership",
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows: aggregate EV/PnL positive, at least two EV-improved windows, "
                "zero EV-regressed windows, survival >= 5%, trade_count_sum >= 58, candidate trades >= 3 across >= 2 windows, "
                "and max DD worse <= 0.5pp"
            ),
            "5_reproducibility": f".venv\\Scripts\\python.exe quant\\experiments\\{STEM}.py",
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md fixed windows, using cached augmented OHLCV "
                "only for non-core candidate coverage from exp-20260501-008"
            ),
            "windows": prior.WINDOWS,
            "config": {"REGIME_AWARE_EXIT": True, "REPLAY_PARTIAL_REDUCES": True},
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_aggregate": prior.base._aggregate(before_metrics),
            "baseline_alignment": baseline_alignment,
            "passed": baseline_alignment["passed"],
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "data/state/universe/universe_registry.json pilot_sleeve",
                "data/state/universe/universe_registry.json theme_segment",
                "cached augmented OHLCV snapshot ohlcv[ticker]",
                "risk_engine.SECTOR_MAP candidate classification",
            ],
            "passed": gate2["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_expansion": True,
            "minimum_after_survival_rate": min(
                row["delta_metrics"]["aggregate_after"]["survival_rate_min"]
                for row in variants
            ),
            "passed": all(
                row["delta_metrics"]["aggregate_after"]["survival_rate_min"] >= 0.05
                for row in variants
            ),
        },
        "gate4": {
            "passed": bool(accepted),
            "accepted_variants": [row["variant"] for row in accepted],
            "selected_variant": selected_summary.get("variant"),
            "selected_gate4": selected_summary.get("gate4"),
        },
        "variant_summary": _variant_summary(variants),
        "selected_variant": selected,
        "variants": variants,
        "before_metrics": before_metrics,
        "after_metrics": selected_summary.get("after_metrics"),
        "delta_metrics": selected_summary.get("delta_metrics"),
        "expected_value_score_delta": selected_summary.get("expected_value_score_delta"),
        "total_pnl_delta": selected_summary.get("total_pnl_delta"),
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM ranking is not changed; this is a deterministic candidate-pool "
                "governance test using replayable registry and OHLCV fields."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_requirement": (
                "If a segment variant is pursued later, add it first through a "
                "default-off paper sleeve or explicit universe-governance policy "
                "with forward replacement value and parity coverage."
            ),
        },
        "production_impact_closeout": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "Do not promote AI infra pilot names into core from cached historical segments. "
            "Use forward AI_INFRA_AGGRESSIVE replacement-value evidence or a broader PIT OHLCV universe before retrying."
        ),
        "related_files": [
            f"quant/experiments/{STEM}.py",
            _repo_rel(OUT_JSON),
            _repo_rel(DOC_LOG),
            _repo_rel(DOC_TICKET),
            _repo_rel(DOC_ARTIFACT),
            _repo_rel(EXPERIMENT_LOG_JSONL),
        ],
    }
    payload["artifact_markdown"] = _markdown(payload)
    return payload


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(DOC_LOG, payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "selected_variant": payload["gate4"]["selected_variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "updated_at": payload["timestamp"],
    }
    _write_json(DOC_TICKET, ticket)
    DOC_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    DOC_ARTIFACT.write_text(_markdown(payload) + "\n", encoding="utf-8")
    jsonl_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"variants", "artifact_markdown"}
    }
    _upsert_jsonl(EXPERIMENT_LOG_JSONL, jsonl_payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "gate1_passed": payload["gate1"]["passed"],
                    "gate4_passed": payload["gate4"]["passed"],
                    "selected_variant": payload["gate4"]["selected_variant"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "variant_summary": payload["variant_summary"],
                    "production_impact": payload["production_impact_closeout"],
                    "anti_js": payload["parameters"]["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
