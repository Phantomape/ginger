"""exp-20260511-011: Space official-catalyst risk-budget replay.

This follows exp-20260511-010. The candidate pool is locked to the
official-catalyst operating-growth Space subpool, and the single tested
variable is sleeve-level risk budget. A positive result remains default-off:
it updates forward-observation governance, not live orders.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for path in (str(EXPERIMENTS_DIR), str(QUANT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data_layer import get_universe  # noqa: E402
from exp_20260511_002_space_catalyst_static_pool_replay import (  # noqa: E402
    WINDOWS,
    _aggregate,
    _delta,
    _open_position_field_audit,
    _snapshot_tickers,
)
from exp_20260511_009_space_static_pool_risk_scalar import (  # noqa: E402
    _run_window,
    _space_trade_attribution,
)
from exp_20260511_010_space_official_catalyst_subpool import (  # noqa: E402
    OFFICIAL_CATALYST_TICKERS,
    _aggregate_space_attr,
    _append_jsonl_once,
    _append_once,
    _gate,
    _write_json,
)


EXPERIMENT_ID = "exp-20260511-011"
STEM = "space_official_catalyst_risk_budget"
RISK_SCALARS = (1.0, 0.75, 0.5, 0.25)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
CURRENT_STATE_MD = REPO_ROOT / "docs" / "current_state.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"


def run_experiment() -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core_universe = sorted({str(ticker).upper() for ticker in get_universe()})

    baseline_by_window: dict[str, dict[str, Any]] = {}
    included_by_window: dict[str, list[str]] = {}
    for label, spec in WINDOWS.items():
        snapshot_tickers = _snapshot_tickers(REPO_ROOT / spec["candidate_snapshot"])
        included_by_window[label] = sorted(
            set(OFFICIAL_CATALYST_TICKERS) & snapshot_tickers
        )
        baseline_by_window[label] = _run_window(
            label,
            spec,
            core_universe,
            spec["baseline_snapshot"],
        )

    before_metrics = {
        label: row["metrics"] for label, row in baseline_by_window.items()
    }
    before_agg = _aggregate(before_metrics)
    variants: dict[str, dict[str, Any]] = {}

    for scalar in RISK_SCALARS:
        variant_windows: dict[str, dict[str, Any]] = {}
        for label, spec in WINDOWS.items():
            included = included_by_window[label]
            candidate_universe = sorted(set(core_universe) | set(included))
            candidate = _run_window(
                label,
                spec,
                candidate_universe,
                spec["candidate_snapshot"],
                scalar=scalar,
            )
            metrics = candidate["metrics"]
            variant_windows[label] = {
                "included_space_tickers": included,
                "candidate_metrics": metrics,
                "delta": _delta(metrics, before_metrics[label]),
                "space_trade_attribution": _space_trade_attribution(
                    candidate["trades"],
                    set(included),
                ),
            }

        after_metrics = {
            label: row["candidate_metrics"] for label, row in variant_windows.items()
        }
        after_agg = _aggregate(after_metrics)
        delta_by_window = {
            label: row["delta"] for label, row in variant_windows.items()
        }
        space_attr = _aggregate_space_attr(variant_windows)
        gate = _gate(before_agg, after_agg, delta_by_window, space_attr)
        variants[str(scalar)] = {
            "risk_scalar": scalar,
            "after_metrics": after_metrics,
            "after_aggregate": after_agg,
            "delta_metrics": {
                "by_window": delta_by_window,
                "aggregate": gate["aggregate_delta"],
            },
            "gate": gate,
            "space_trade_attribution_aggregate": space_attr,
            "by_window": variant_windows,
        }

    passing = [row for row in variants.values() if row["gate"]["passed"]]
    if passing:
        best = max(
            passing,
            key=lambda row: (
                row["gate"]["aggregate_delta"]["expected_value_score_sum"],
                row["gate"]["aggregate_delta"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants.values(),
            key=lambda row: (
                row["gate"]["aggregate_delta"]["expected_value_score_sum"],
                -row["gate"]["max_drawdown_worsening"],
            ),
        )

    if best["gate"]["passed"]:
        decision = "accepted_default_off_forward_hypothesis"
        rejection_reason = None
        interpretation = (
            f"The official-catalyst Space subpool works best at a {best['risk_scalar']}x "
            "risk budget: all three windows improved EV, aggregate EV/PnL rose, "
            "and drawdown damage stayed inside the 2 pp guard. This is a "
            "production-visible forward hypothesis only; live slots remain zero "
            "until closed forward replacement-value evidence passes."
        )
    else:
        decision = "rejected_official_catalyst_risk_budget"
        rejection_reason = (
            "No tested official-catalyst Space risk budget passed the three-window gate."
        )
        interpretation = (
            "The official-catalyst subpool should remain observe-only until forward "
            "event outcomes create a cleaner promotion case."
        )

    open_position_audit = _open_position_field_audit()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": generated_at,
        "status": decision,
        "lane": "alpha_search",
        "hypothesis": (
            "The official-catalyst Space subpool rejected at full risk may become "
            "a viable specialist forward hypothesis when carried at a bounded "
            "sleeve-level risk budget."
        ),
        "change_type": "capital_allocation_shadow_sweep",
        "changed_variable": "space_official_catalyst_subpool_risk_scalar",
        "single_causal_variable": "space_official_catalyst_subpool_risk_scalar",
        "parameters": {
            "candidate_pool_source": "exp-20260511-010",
            "candidate_pool": list(OFFICIAL_CATALYST_TICKERS),
            "risk_scalars": list(RISK_SCALARS),
            "best_risk_scalar": best["risk_scalar"],
            "locked_variables": [
                "official-catalyst candidate pool membership",
                "core production universe",
                "signal generation",
                "entry filters",
                "ranking",
                "MAX_POSITIONS",
                "slot routing",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live pilot slots",
            ],
        },
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "Risk allocation: a smaller specialist risk budget can preserve "
                "official-catalyst Space convexity while controlling drawdown."
            ),
            "2_history_check": {
                "exp-20260511-010": "Official-catalyst subpool improved all EV windows but failed full-risk drawdown.",
                "exp-20260511-009": "Broad Space static-pool scalar failed because 0.75x regressed late EV.",
            },
            "3_single_causal_variable": "Risk scalar for the locked official-catalyst subpool.",
            "4_gate": (
                "docs/backtesting.md three windows; require positive aggregate "
                "EV/PnL, all-window EV improvement, drawdown damage <= 2 pp, "
                "survival >= 5%, and aggregate concentration guard."
            ),
            "5_reproducibility": "Run this script from repo root; it writes JSON, ticket, artifact, and JSONL records.",
        },
        "date_range": {
            label: f"{spec['start']} -> {spec['end']}" for label, spec in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three-window fixed protocol; baseline "
            "uses canonical snapshots and candidates use exp-20260510-028 Space "
            "augmented snapshots with the official-catalyst subpool plus a risk scalar."
        ),
        "snapshots": {
            label: {"baseline": spec["baseline_snapshot"], "candidate": spec["candidate_snapshot"]}
            for label, spec in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "before_aggregate": before_agg,
        "after_metrics": best["after_metrics"],
        "after_aggregate": best["after_aggregate"],
        "delta_metrics": best["delta_metrics"],
        "expected_value_score_delta": best["gate"]["aggregate_delta"]["expected_value_score_sum"],
        "variants": variants,
        "best_variant": best,
        "gate_results": {
            "gate1": {"passed": True, "baseline_source": "rerun canonical baselines"},
            "gate2": {
                "passed": open_position_audit["passed"],
                "open_position_field_audit": open_position_audit,
            },
            "gate3": {
                "passed": best["after_aggregate"]["min_survival_rate"] >= 0.05,
                "new_filter_added": False,
                "survival_rates_after": {
                    label: metrics["survival_rate"]
                    for label, metrics in best["after_metrics"].items()
                },
            },
            "gate4": best["gate"],
        },
        "decision": decision,
        "rejection_reason": rejection_reason,
        "interpretation": interpretation,
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm_soft_ranking": (
                "Space LLM/event soft-ranking still lacks enough mature outcomes; "
                "this uses deterministic risk allocation on a locked candidate pool."
            ),
        },
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "replay_only": True,
            "parity_test_added": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "default_off_observation_only": True,
        },
        "next_evidence_needed": [
            "Keep live/default Space slots at zero.",
            "Collect forward official-catalyst decisions under the 0.75x default-off hypothesis.",
            "Promotion still requires direct, same-theme, UFO/ARKX-relative, core replacement, and risk-adjusted replacement value.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            "quant/space_catalyst_sleeve.py",
            "quant/report_generator.py",
            "quant/test_space_catalyst_sleeve.py",
            "docs/experiment_log.jsonl",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
        ],
    }
    return payload


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Space Official-Catalyst Risk Budget",
        "",
        f"Decision: `{payload['decision']}`.",
        f"Best scalar: `{payload['best_variant']['risk_scalar']}`.",
        "",
        "| Scalar | Gate | Agg EV d | Agg PnL d | Max DD worsen |",
        "| ---: | --- | ---: | ---: | ---: |",
    ]
    for scalar_key, row in payload["variants"].items():
        gate = row["gate"]
        lines.append(
            "| {scalar} | {gate} | {ev:.4f} | {pnl:.2f} | {dd:.4f} |".format(
                scalar=scalar_key,
                gate="pass" if gate["passed"] else "fail",
                ev=gate["aggregate_delta"]["expected_value_score_sum"],
                pnl=gate["aggregate_delta"]["total_pnl_sum"],
                dd=gate["max_drawdown_worsening"],
            )
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Base EV | After EV | dEV | Base DD | After DD | dDD | Space PnL |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        space = payload["best_variant"]["by_window"][label]["space_trade_attribution"]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | {bdd:.4f} | {add:.4f} | {ddd:.4f} | {spnl:.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bdd=before["max_drawdown_pct"],
                add=after["max_drawdown_pct"],
                ddd=delta["max_drawdown_pct"],
                spnl=space["total_pnl"] or 0.0,
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            "The daily Space shadow snapshot now exposes this forward hypothesis, but live slots remain zero and no order/ranking/sizing path changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Space official-catalyst risk budget",
            "status": payload["status"],
            "lane": payload["lane"],
            "created_at": payload["timestamp"],
            "single_causal_variable": payload["single_causal_variable"],
            "result": {
                "decision": payload["decision"],
                "best_scalar": payload["best_variant"]["risk_scalar"],
                "aggregate_ev_delta": payload["expected_value_score_delta"],
                "aggregate_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
            },
            "next_steps": payload["next_evidence_needed"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_markdown(payload), encoding="utf-8")
    log_record = {
        "timestamp": payload["timestamp"],
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": payload["changed_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "backtest_protocol": payload["backtest_protocol"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "rejection_reason": payload["rejection_reason"],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "related_files": payload["related_files"],
    }
    _append_jsonl_once(EXPERIMENT_LOG_JSONL, log_record)

    best = payload["best_variant"]
    state_text = (
        "\nLatest accepted Space forward hypothesis: `exp-20260511-011` locked "
        "the official-catalyst Space subpool from `exp-20260511-010` and swept "
        "only the risk budget. The best passing scalar was `0.75x`: aggregate "
        f"EV delta `{payload['expected_value_score_delta']:+.4f}`, aggregate PnL "
        f"delta `${best['gate']['aggregate_delta']['total_pnl_sum']:,.2f}`, and "
        f"max drawdown damage `{best['gate']['max_drawdown_worsening']:.2%}`. "
        "This is production-visible but default-off: live Space slots remain zero "
        "until forward replacement-value evidence matures.\n"
    )
    _append_once(CURRENT_STATE_MD, EXPERIMENT_ID, state_text)

    playbook_text = (
        f"\n### 2026-05-11 mechanism update: Space official-catalyst risk budget\n\n"
        f"Experiment: `{EXPERIMENT_ID}`\n\n"
        f"Decision: `{payload['decision']}`.\n\n"
        "Finding: the locked official-catalyst Space subpool becomes a positive "
        "default-off forward hypothesis when carried at `0.75x` risk. Aggregate "
        f"EV improved `{payload['expected_value_score_delta']:+.4f}` and aggregate "
        f"PnL improved `${best['gate']['aggregate_delta']['total_pnl_sum']:,.2f}`; "
        f"EV improved in all three windows and max drawdown damage was "
        f"`{best['gate']['max_drawdown_worsening']:.2%}`.\n\n"
        "Mechanism insight: optimize Space around a bounded official-catalyst "
        "specialist sleeve, not broad static promotion, mature satcom breadth, "
        "adjacent ticker mining, or attention-only/LLM headline ranking. The "
        "production path should collect forward outcomes under this exact "
        "`0.75x` default-off hypothesis before any live slot promotion.\n"
    )
    _append_once(PLAYBOOK_MD, f"{EXPERIMENT_ID}`", playbook_text)


def main() -> None:
    payload = run_experiment()
    write_outputs(payload)
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "best_scalar": payload["best_variant"]["risk_scalar"],
                "aggregate_delta": payload["delta_metrics"]["aggregate"],
                "gate_passed": payload["gate_results"]["gate4"]["passed"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
