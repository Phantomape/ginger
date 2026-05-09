"""exp-20260509-006 event bundle current-stack revalidation.

Alpha search, replay-only. Recent mechanism logs make LLM soft-ranking,
earnings/SEC directional enrichment, macro sleeves, and core threshold/ranking
sweeps either data-limited or recently rejected. The strongest remaining
candidate-pool evidence is the frozen default-off event overlay bundle.

This experiment changes one causal variable in replay: add the already-frozen
external event queues as independent satellite overlays on top of the current
accepted core stack. It does not alter production orders, core A/B entries,
ranking, sizing, exits, add-ons, LLM/news behavior, or event-source thresholds.
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

from experiments.exp_20260504_049_default_off_event_overlay_bundle import (  # noqa: E402
    EVENT_NOTIONAL,
    HOLD_DAYS,
    ROUND_TRIP_COST_PCT,
    WINDOWS,
    _aggregate_delta,
    _combined_metrics,
    _core_metrics,
    _event_equity_curve,
    _gate4,
    _load_core_result,
    _load_event_trades,
    _source_summary,
)


EXPERIMENT_ID = "exp-20260509-006"
STEM = "event_bundle_current_stack_revalidation"
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


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# exp-20260509-006 Event Bundle Current-Stack Revalidation",
        "",
        "Decision: `{}`".format(payload["decision"]),
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Three-Window Result",
        "",
        "| Window | Core EV | Core+Event EV | Delta EV | Core PnL | Core+Event PnL | Delta PnL | Event trades | Event PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        event = payload["event_overlay"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:,.2f} | {trades} | ${epnl:,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                trades=event["event_trade_count"],
                epnl=event["event_pnl"],
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
            "",
            "## Decision Rationale",
            "",
            payload["decision_rationale"],
            "",
            "## Production Impact",
            "",
            "Replay only. Production and default backtest order paths are unchanged. A positive live-capital version still needs a shared trade-enabled event adapter, run/backtester parity tests, and forward paper replacement-value evidence.",
            "",
            "## Source Contribution",
            "",
            "```json",
            json.dumps(payload["source_contribution"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def build_payload() -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    event_trades_by_window, coverage, prices = _load_event_trades()
    before_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    event_overlay: dict[str, dict[str, Any]] = OrderedDict()
    source_contribution: dict[str, Any] = OrderedDict()

    for label, window in WINDOWS.items():
        core_result = _load_core_result(window)
        event_trades = event_trades_by_window[label]
        event_curve = _event_equity_curve(
            event_trades,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        before_metrics[label] = _core_metrics(core_result)
        after_metrics[label] = _combined_metrics(core_result, event_curve, event_trades)
        source_contribution[label] = _source_summary(event_trades)
        event_overlay[label] = {
            "event_trade_count": len(event_trades),
            "event_pnl": _round(
                sum(float(trade.get("pnl") or 0.0) for trade in event_trades),
                2,
            ),
            "event_win_rate": _round(
                sum(1 for trade in event_trades if float(trade.get("pnl") or 0.0) > 0)
                / len(event_trades)
                if event_trades
                else None,
                4,
            ),
            "event_trades": [
                {
                    "source": trade.get("source"),
                    "ticker": trade.get("ticker"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": trade.get("pnl"),
                    "net_return_pct": trade.get("net_return_pct"),
                }
                for trade in event_trades
            ],
        }

    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4_by_window = OrderedDict(
        (label, _gate4(before_metrics[label], after_metrics[label]))
        for label in WINDOWS
    )
    passed = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and (
            (delta["aggregate_ev_delta_pct"] is not None and delta["aggregate_ev_delta_pct"] > 0.10)
            or (delta["aggregate_pnl_delta_pct"] is not None and delta["aggregate_pnl_delta_pct"] > 0.05)
            or any(row["passes_sharpe"] for row in gate4_by_window.values())
            or any(row["passes_drawdown"] for row in gate4_by_window.values())
        )
    )
    decision = "accepted_direction_paper_only" if passed else "rejected"
    decision_rationale = (
        "Accepted as the current strongest alpha direction for forward paper optimization: "
        "the frozen event bundle improves EV in all three canonical windows and clears "
        "aggregate materiality versus the current core stack. It is not promoted to "
        "live/default orders because replay-only event queues still need shared adapter "
        "parity and forward replacement-value evidence."
        if passed
        else "Rejected: the frozen event bundle no longer clears the three-window Gate 4 standard versus the current core stack."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "current_stack_event_bundle_revalidation",
        "mechanism_family": "external_event_candidate_pool",
        "hypothesis": (
            "The highest-value alpha direction now is candidate-pool extension via the frozen "
            "default-off event bundle, because it adds independent event-driven satellite "
            "returns without consuming core A/B slots."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool_extension",
            "entry_exit_ranking_or_allocation": "satellite allocation",
            "why_this_now": (
                "Recent logs make LLM soft-ranking and earnings/SEC directional enrichment "
                "data-limited, while core threshold/ranking/slot surfaces and macro sleeves "
                "have been rejected or saturated. Event bundle replay remains the strongest "
                "positive multi-window evidence."
            ),
        },
        "single_causal_variable": (
            "Add frozen default-off event bundle as independent replay satellite overlay"
        ),
        "parameters": {
            "event_sources": [
                "form4_meaningful_purchase",
                "sec_negative_reaction",
                "sec_governance_procedural",
            ],
            "event_notional_usd": EVENT_NOTIONAL,
            "per_source_max_positions": 1,
            "hold_days": HOLD_DAYS,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "LLM prompt and replay",
                "news veto",
                "event thresholds",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "checked_sources": [
                "docs/alpha-optimization-playbook.md",
                "docs/experiment_log.jsonl",
                "docs/experiments/artifacts",
                "docs/backtesting.md",
            ],
            "recent_no_go_or_blocked_surfaces": [
                "LLM soft-ranking outcome data remains too sparse for promotion",
                "earnings and filing directional fields remain incomplete",
                "core threshold/ranking/slot sweeps have repeated rejections",
                "macro ETF passive overlays and XLE/USO confirmation were rejected",
                "event source/notional/holding-period tuning should not be repeated on the same sample",
            ],
            "why_not_simple_repeat": (
                "This does not retune the event bundle. It revalidates whether the frozen "
                "bundle is still the strongest alpha direction after the current accepted core stack."
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4": {
            "protocol": "docs/backtesting.md canonical three-window evaluation",
            "by_window": gate4_by_window,
            "passed": passed,
            "rule": "EV first; require multi-window improvement, no EV regression, and one materiality trigger.",
        },
        "event_overlay": event_overlay,
        "source_contribution": source_contribution,
        "coverage": coverage,
        "expected_value_score_delta": {
            label: delta["by_window"][label]["expected_value_score"]
            for label in WINDOWS
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "default_backtest_strategy_changed": False,
            "production_order_path_changed": False,
            "promotion_blocker_if_positive": (
                "Before live capital, implement a shared event-candidate/order adapter "
                "used by run.py and backtester.py, add parity tests, and collect forward paper outcomes."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "why_no_llm_alpha": (
                "LLM soft-ranking is intentionally skipped because outcome data is still "
                "insufficient; this run searches another alpha surface instead."
            ),
        },
        "decision_rationale": decision_rationale,
        "rejection_reason": None if passed else decision_rationale,
        "why_not_other_attractive_points": (
            "I did not run another core threshold, add-on heat, macro ETF, or same-sample "
            "event filter sweep because recent mechanism records already mark those as "
            "saturated, rejected, or data-limited."
        ),
        "risk_of_change": (
            "Sparse event families can look stronger in replay than forward. The risk is "
            "over-promoting a bundled event sleeve before paper outcomes prove replacement value."
        ),
        "next_action": (
            "Keep optimizing the event bundle as a default-off paper alpha surface, then only "
            "promote live orders after shared run/backtester policy and forward paper evidence."
        ),
        "related_files": [
            str(Path(__file__).relative_to(REPO_ROOT)).replace("\\", "/"),
            str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(TICKET_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
        ],
    }


def main() -> int:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event bundle current-stack revalidation",
            "status": payload["status"],
            "decision": payload["decision"],
            "summary": payload["decision_rationale"],
            "created_at": payload["timestamp"],
            "artifact": str(ARTIFACT_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        },
    )
    _write_text(ARTIFACT_MD, _artifact_markdown(payload))
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "aggregate_delta": payload["delta_metrics"],
                    "production_impact": payload["production_impact"],
                    "artifact": str(ARTIFACT_MD),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
