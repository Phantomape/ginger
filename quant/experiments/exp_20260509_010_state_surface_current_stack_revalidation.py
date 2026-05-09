"""exp-20260509-010 state-surface satellite current-stack revalidation.

Alpha search, replay-only. Revalidates the previously promising
state-surface satellite sleeve after the accepted stack refresh. The tested
causal variable is still one bounded independent candidate-pool sleeve:
top-three non-overlapping state-surface candidates, next-open entry, fixed
20-trading-day hold, and three active paper positions.

No production strategy code, live/default orders, core A/B ranking, sizing,
exits, add-ons, LLM, or news logic is changed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260507_016_state_surface_satellite_replay as base


EXPERIMENT_ID = "exp-20260509-010"
STEM = "state_surface_current_stack_revalidation"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(base._safe(payload), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _retag_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    payload["experiment_id"] = EXPERIMENT_ID
    payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["change_type"] = "state_surface_satellite_current_stack_revalidation"
    payload["hypothesis"] = (
        "After the current accepted stack refresh, the non-overlapping "
        "state-surface satellite sleeve may still improve EV as a bounded "
        "candidate-pool extension without touching core A/B logic."
    )
    payload["alpha_hypothesis"] = {
        "category": "candidate_pool_extension",
        "entry_exit_ranking_or_allocation": "satellite entry/allocation",
        "why_this_now": (
            "LLM soft-ranking and earnings/revision ranking remain data-limited, "
            "nearby gap/reclaim/add-on heat/core retunes are rejected or below "
            "materiality, and this tests a different already-observed "
            "state-surface alpha family rather than retuning the event bundle."
        ),
    }
    payload["historical_experiment_check"] = {
        "direct_parent": {
            "exp-20260507-016": (
                "State-surface satellite was promising replay-only on the prior "
                "stack, but not current-stack validated."
            ),
            "exp-20260507-017": (
                "Dropping balanced_state_leadership regressed late_strong and was "
                "rejected; this run keeps the frozen full surface definition."
            ),
        },
        "nearby_rejected_or_blocked": {
            "LLM soft-ranking": "Too few production-aligned ranking/outcome joins.",
            "earnings/revisions": "Too few multi-window candidate touches.",
            "gap/reclaim": "Recent executable replays failed multi-window gates.",
            "event source/notional retunes": (
                "Source pruning and rotation-surface over-scaling were rejected "
                "or too concentrated."
            ),
            "staged entry/add-on reserves": "Rejected or inert on the current stack.",
        },
        "mechanism_insight_conflict": (
            "No conflict: this is not a threshold retune, not a source/notional "
            "event-bundle sweep, not a broad noisy universe expansion, and not an "
            "LLM hard-risk change."
        ),
        "why_not_simple_repeat": (
            "The prior positive run used older accepted-stack metrics. This run "
            "replays the same frozen surface sleeve on the refreshed current "
            "stack with the same three canonical windows."
        ),
    }
    payload["parameters"]["locked_variables"] = sorted(
        set(payload["parameters"].get("locked_variables") or [])
        | {
            "event bundle source definitions",
            "event bundle notional/scalars",
            "pilot sleeves",
            "production adapters",
        }
    )
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "parity_test_added": False,
        "replay_only": True,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "default_backtest_strategy_changed": False,
        "production_order_path_changed": False,
        "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
        "parity_note": (
            "Production already emits the default-off state-surface paper sleeve. "
            "This experiment only replays historical paper trades; a positive "
            "trade-enabled version still requires a shared run/backtester adapter "
            "and parity tests."
        ),
        "promotion_blocker_if_positive": (
            "Before live/default orders, implement an explicit shared "
            "state-surface trade adapter consumed by run.py and backtester.py, "
            "add parity tests, and require closed forward replacement-value "
            "outcomes."
        ),
    }
    if payload.get("decision") == "promising_replay_only":
        payload["decision_rationale"] = (
            "Promising replay-only on the current stack: the frozen state-surface "
            "satellite improved the majority of canonical windows under the "
            "existing Gate 4/concentration guard. It remains paper-only because "
            "live/default orders require a shared adapter, parity tests, and "
            "closed forward replacement-value evidence."
        )
        payload["rejection_reason"] = None
        payload["status"] = "promising_replay_only_current_stack"
        payload["decision"] = "promising_replay_only_current_stack"
    else:
        payload["decision_rationale"] = (
            "Rejected on the current stack: the frozen state-surface satellite "
            "did not clear the three-window Gate 4 standard without EV "
            "regression, materiality, and concentration controls."
        )
        payload["rejection_reason"] = payload["decision_rationale"]
        payload["status"] = "rejected"
        payload["decision"] = "rejected"
    payload["next_action"] = (
        "Use the result to rank state-surface versus event-bundle candidate-pool "
        "leads. Do not route state-surface paper candidates to live/default "
        "orders without a shared adapter and forward closed outcomes."
    )
    payload["why_not_other_attractive_points"] = (
        "I skipped LLM ranking, earnings revisions, gap/reclaim, add-on heat, "
        "staged entry, and event-bundle notional/source retunes because recent "
        "records mark them data-limited, rejected, concentrated, or below "
        "materiality."
    )
    payload["risk_of_change"] = (
        "The surface can over-select crowded momentum leaders; replay-only "
        "paper results may overstate live replacement value until forward "
        "closed outcomes exist."
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(ARTIFACT_MD),
        "docs/experiment_log.jsonl",
        "docs/alpha-optimization-playbook.md",
    ]
    return payload


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-010 State-Surface Current-Stack Revalidation",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "Alpha search, replay-only. Revalidates the frozen state-surface satellite sleeve on the refreshed accepted stack.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Sleeve trades | Sleeve PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {trades} | ${epnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=sleeve["selected_trade_count"],
                epnl=sleeve["selected_pnl"],
            )
        )
    agg = payload["delta_metrics"]
    lines.extend(
        [
            "",
            "## Aggregate Gate",
            "",
            "- EV sum: {:.4f} -> {:.4f} ({:+.4f}, {:+.2%})".format(
                agg["baseline_ev_sum"],
                agg["after_ev_sum"],
                agg["aggregate_ev_delta"],
                agg["aggregate_ev_delta_pct"] or 0.0,
            ),
            "- PnL sum: ${:,.2f} -> ${:,.2f} ({:+,.2f}, {:+.2%})".format(
                agg["baseline_pnl_sum"],
                agg["after_pnl_sum"],
                agg["aggregate_pnl_delta"],
                agg["aggregate_pnl_delta_pct"] or 0.0,
            ),
            "- EV windows improved/regressed: {}/{}".format(
                agg["windows_ev_improved"],
                agg["windows_ev_regressed"],
            ),
            "- Single-ticker positive share: {}".format(
                payload["gate4"].get("single_ticker_positive_share")
            ),
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Surface Contribution",
            "",
            "```json",
            json.dumps(
                payload["surface_contribution"],
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
            "## Production Impact",
            "",
            "No live/default orders, core A/B behavior, LLM, news, or production adapter changed. Any positive trade-enabled version must be implemented through a shared run/backtester adapter with parity tests and forward replacement-value evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "State-surface current-stack revalidation",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "next_action": payload["next_action"],
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))

    compact = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "historical_experiment_check": payload["historical_experiment_check"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "delta_metrics": payload["delta_metrics"],
        "gate4": payload["gate4"],
        "surface_sleeve": {
            label: {
                "raw_candidate_count": row["raw_candidate_count"],
                "selected_trade_count": row["selected_trade_count"],
                "selected_pnl": row["selected_pnl"],
                "selected_win_rate": row["selected_win_rate"],
                "surface_summary": row["surface_summary"],
                "skipped_reason_counts": row["skipped_reason_counts"],
            }
            for label, row in payload["surface_sleeve"].items()
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "risk_of_change": payload["risk_of_change"],
        "related_files": payload["related_files"],
    }
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(base._safe(compact), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = _retag_payload(base.build_payload())
    persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "delta_metrics": payload["delta_metrics"],
                    "gate4": payload["gate4"],
                    "surface_trades": {
                        label: payload["surface_sleeve"][label]["selected_trade_count"]
                        for label in base.WINDOWS
                    },
                    "production_impact": payload["production_impact"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
