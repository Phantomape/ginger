"""exp-20260507-017 state-surface conviction prune replay.

Alpha search follow-up to exp-20260507-016. The only causal variable is surface
eligibility inside the replay-only state-aware satellite sleeve: exclude the
low-conviction balanced-state surface and keep the rotation/broad-breadth
surfaces unchanged.

No production strategy code, live order path, core ranking, sizing, exits,
universe membership, LLM, or news logic is changed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from experiments import exp_20260507_016_state_surface_satellite_replay as base  # noqa: E402


EXP_ID = "exp-20260507-017"
STEM = "state_surface_conviction_prune"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
AUDIT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

ALLOWED_SURFACES = {
    "broad_breadth_trend_persistence",
    "rotation_breakout_leadership",
}
EXCLUDED_SURFACES = {"balanced_state_leadership"}
PREVIOUS_FULL_REPLAY = (
    REPO_ROOT / "data" / "experiments" / "exp-20260507-016" / "state_surface_satellite_replay.json"
)

ORIGINAL_RAW_CANDIDATES = base._raw_candidates


def _patch_base_paths() -> None:
    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.AUDIT_MD = AUDIT_MD


def _raw_candidates_without_balanced(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    rows = ORIGINAL_RAW_CANDIDATES(*args, **kwargs)
    return [row for row in rows if str(row.get("surface") or "") in ALLOWED_SURFACES]


def _metric_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": _round(
            float(after.get("expected_value_score") or 0.0)
            - float(before.get("expected_value_score") or 0.0),
            4,
        ),
        "total_pnl": _round(
            float(after.get("total_pnl") or 0.0) - float(before.get("total_pnl") or 0.0),
            2,
        ),
        "max_drawdown_pct": _round(
            float(after.get("max_drawdown_pct") or 0.0)
            - float(before.get("max_drawdown_pct") or 0.0),
            4,
        ),
        "trade_count": int(after.get("trade_count") or 0) - int(before.get("trade_count") or 0),
        "win_rate": _round(float(after.get("win_rate") or 0.0) - float(before.get("win_rate") or 0.0), 4),
    }


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _load_previous_full_comparison(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not PREVIOUS_FULL_REPLAY.exists():
        return None
    prior = json.loads(PREVIOUS_FULL_REPLAY.read_text(encoding="utf-8"))
    comparison: dict[str, Any] = OrderedDict()
    for label in base.WINDOWS:
        prior_after = (prior.get("after_metrics") or {}).get(label)
        current_after = (payload.get("after_metrics") or {}).get(label)
        if not isinstance(prior_after, dict) or not isinstance(current_after, dict):
            continue
        comparison[label] = _metric_delta(prior_after, current_after)
    prior_delta = prior.get("delta_metrics") or {}
    current_delta = payload.get("delta_metrics") or {}
    comparison["aggregate"] = {
        "full_replay_ev_delta": prior_delta.get("aggregate_ev_delta"),
        "pruned_replay_ev_delta": current_delta.get("aggregate_ev_delta"),
        "incremental_ev_delta_vs_full": _round(
            float(current_delta.get("aggregate_ev_delta") or 0.0)
            - float(prior_delta.get("aggregate_ev_delta") or 0.0),
            4,
        ),
        "full_replay_pnl_delta": prior_delta.get("aggregate_pnl_delta"),
        "pruned_replay_pnl_delta": current_delta.get("aggregate_pnl_delta"),
        "incremental_pnl_delta_vs_full": _round(
            float(current_delta.get("aggregate_pnl_delta") or 0.0)
            - float(prior_delta.get("aggregate_pnl_delta") or 0.0),
            2,
        ),
    }
    return comparison


def build_payload() -> dict[str, Any]:
    _patch_base_paths()
    base._raw_candidates = _raw_candidates_without_balanced
    payload = base.build_payload()

    payload.update(
        {
            "experiment_id": EXP_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "change_type": "state_surface_satellite_surface_prune",
            "mechanism_family": "state_aware_candidate_pool_extension",
            "hypothesis": (
                "The replay-only state-aware satellite can improve robustness by excluding "
                "the low-conviction balanced-state surface while keeping the rotation and "
                "broad-breadth surfaces unchanged."
            ),
            "alpha_hypothesis": {
                "category": "entry/allocation",
                "why_this_now": (
                    "LLM soft-ranking, earnings, SEC text severity, and event source pruning "
                    "are currently blocked or recently rejected. The prior state-surface replay "
                    "was the strongest remaining alpha lead, but its balanced surface lost money "
                    "in every canonical window."
                ),
            },
            "why_not_other_attractive_points": (
                "I did not retune top-N, hold days, notional, core slots, exits, or risk "
                "multipliers because that would mix causality with the surface-eligibility test. "
                "LLM soft-ranking and earnings were skipped due to insufficient usable replay "
                "or rejected evidence."
            ),
            "risk_of_change": (
                "The prune may throw away balanced-regime winners and can concentrate the sleeve "
                "into high-momentum breadth/rotation names; no live promotion is claimed without "
                "a shared production adapter and parity tests."
            ),
            "next_action": (
                "If this remains promising, the next valid step is a default-off shared "
                "state-surface paper adapter in run.py/backtester.py, not a live trading switch."
            ),
        }
    )
    payload["parameters"].update(
        {
            "single_causal_variable": "exclude balanced_state_leadership from satellite surface eligibility",
            "allowed_surfaces": sorted(ALLOWED_SURFACES),
            "excluded_surfaces": sorted(EXCLUDED_SURFACES),
        }
    )
    payload["historical_experiment_check"] = {
        "similar_experiments": {
            "exp-20260507-005": "Observed-only state-aware surface found a non-overlapping candidate lead, but no executable policy.",
            "exp-20260507-016": "Full satellite replay was promising but balanced_state_leadership contributed negative PnL in all three windows.",
            "exp-20260507-012": "Event source pruning failed; this is not event-source pruning and uses a different state-surface mechanism.",
            "exp-20260505-009": "Broad universe expansion failed; this run adds no tickers and stays inside the production universe.",
        },
        "mechanism_no_go_check": [
            "No LLM/prompt change.",
            "No SEC text phrase tuning.",
            "No broad ticker expansion.",
            "No core slot, ranking, sizing, exit, or hold-day change.",
            "No production order change from replay evidence.",
        ],
        "why_not_simple_repeat": (
            "The previous run tested the full three-surface sleeve. This run tests one "
            "pre-identified weak surface removal while all entry timing, capacity, notional, "
            "and hold logic stay frozen."
        ),
    }
    payload["production_impact"] = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "production_impact": "experiment_only_no_live_or_default_backtest_strategy_change",
        "promotion_blocker_if_positive": (
            "Requires a shared state-surface policy adapter consumed by both run.py and "
            "backtester.py plus parity tests before production use."
        ),
    }

    passed = bool((payload.get("gate4") or {}).get("passed_without_regression"))
    if passed:
        payload["decision"] = "promising_replay_only"
        payload["status"] = "promising_replay_only"
        payload["decision_rationale"] = (
            "Promising replay-only: excluding balanced_state_leadership kept the state-surface "
            "satellite positive against the core baseline under the three-window Gate 4 check. "
            "It is not production alpha until a shared run/backtester adapter and parity tests exist."
        )
        payload["rejection_reason"] = None
    else:
        payload["decision"] = "rejected"
        payload["status"] = "rejected"
        payload["decision_rationale"] = (
            "Rejected: excluding balanced_state_leadership did not clear the three-window "
            "Gate 4 standard with material improvement, no EV regression, and concentration controls."
        )
        payload["rejection_reason"] = payload["decision_rationale"]

    payload["full_replay_comparison"] = _load_previous_full_comparison(payload)
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(AUDIT_MD),
        "docs/experiment_log.jsonl",
    ]
    return payload


def _write_report(payload: dict[str, Any]) -> None:
    lines = [
        "# exp-20260507-017 State Surface Conviction Prune",
        "",
        "Replay-only alpha search. Core A/B entries, ranking, sizing, exits, LLM, news, and production orders are unchanged.",
        "",
        "## Tested Variable",
        "",
        "Exclude `balanced_state_leadership`; keep `broad_breadth_trend_persistence` and `rotation_breakout_leadership` unchanged.",
        "",
        "## Three-window result",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL | Sleeve trades | Sleeve PnL | Max DD after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        sleeve = payload["surface_sleeve"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {trades} | ${spnl:,.2f} | {dd:.2%} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=sleeve["selected_trade_count"],
                spnl=sleeve["selected_pnl"],
                dd=after["max_drawdown_pct"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            payload["decision_rationale"],
            "",
            "## Incremental Comparison Versus exp-20260507-016",
            "",
            "```json",
            json.dumps(payload.get("full_replay_comparison"), indent=2, sort_keys=True),
            "```",
            "",
            "## Surface Contribution",
            "",
            "```json",
            json.dumps(payload["surface_contribution"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    base._write_text(AUDIT_MD, "\n".join(lines))


def persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXP_ID,
            "title": "State surface conviction prune",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "related_log": base._repo_rel(LOG_JSON),
            "artifact": base._repo_rel(OUT_JSON),
        },
    )
    _write_report(payload)
    base._append_experiment_log(payload)


def main() -> int:
    payload = build_payload()
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
                    "full_replay_comparison": payload.get("full_replay_comparison", {}).get("aggregate")
                    if payload.get("full_replay_comparison")
                    else None,
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
