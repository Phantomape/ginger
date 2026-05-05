"""Replay the day-2 add-on improving-followthrough quality gate.

This alpha-search experiment tests one existing default-off config hook:
ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH. It does not change production defaults.
If accepted, the same gate must be mirrored in production_parity.py before
promotion.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXP_ID = "exp-20260504-031"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "addon_improving_followthrough.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXP_ID}.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    },
}


def _round(value: Any, digits: int = 6) -> Any:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return round(float(value), digits)
    return value


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    total_pnl = float(result.get("total_pnl") or 0.0)
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": round(total_pnl / 100_000.0, 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _addon_summary(result: dict[str, Any]) -> dict[str, Any]:
    attr = result.get("addon_attribution") or {}
    events = attr.get("events") or []
    status_counts: dict[str, int] = {}
    rejected: list[dict[str, Any]] = []
    executed: list[dict[str, Any]] = []
    for event in events:
        status = str(event.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        row = {
            "ticker": event.get("ticker"),
            "strategy": event.get("strategy"),
            "sector": event.get("sector"),
            "checkpoint_date": event.get("checkpoint_date"),
            "unrealized_pct": event.get("unrealized_pct"),
            "rs_vs_spy": event.get("rs_vs_spy"),
            "day1_unrealized_pct": event.get("day1_unrealized_pct"),
            "day1_rs_vs_spy": event.get("day1_rs_vs_spy"),
            "status": status,
        }
        if status.startswith("rejected_checkpoint"):
            rejected.append(row)
        if status == "executed":
            executed.append(row)
    return {
        "scheduled": attr.get("scheduled"),
        "executed": attr.get("executed"),
        "skipped": attr.get("skipped"),
        "checkpoint_rejected": attr.get("checkpoint_rejected"),
        "status_counts": status_counts,
        "rejected_checkpoint_events": rejected,
        "executed_events": executed,
    }


def _run_window(universe: list[str], window: dict[str, str], config: dict[str, Any]) -> dict[str, Any]:
    result = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        ohlcv_snapshot_path=window["snapshot"],
    ).run()
    return {
        "metrics": _metrics(result),
        "addon_attribution": _addon_summary(result),
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
    ]
    return {
        key: _round((after.get(key) or 0) - (before.get(key) or 0), 6)
        for key in keys
    }


def _aggregate_delta(
    before_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    baseline_ev = sum(float(v["expected_value_score"] or 0) for v in before_metrics.values())
    variant_ev = sum(float(v["expected_value_score"] or 0) for v in after_metrics.values())
    baseline_pnl = sum(float(v["total_pnl"] or 0) for v in before_metrics.values())
    variant_pnl = sum(float(v["total_pnl"] or 0) for v in after_metrics.values())
    by_window = {
        label: _delta(before_metrics[label], after_metrics[label])
        for label in before_metrics
    }
    return {
        "by_window": by_window,
        "baseline_ev_sum": round(baseline_ev, 4),
        "variant_ev_sum": round(variant_ev, 4),
        "aggregate_ev_delta": round(variant_ev - baseline_ev, 4),
        "aggregate_ev_delta_pct": round((variant_ev - baseline_ev) / baseline_ev, 6)
        if baseline_ev
        else None,
        "baseline_pnl_sum": round(baseline_pnl, 2),
        "variant_pnl_sum": round(variant_pnl, 2),
        "aggregate_pnl_delta": round(variant_pnl - baseline_pnl, 2),
        "aggregate_pnl_delta_pct": round((variant_pnl - baseline_pnl) / baseline_pnl, 6)
        if baseline_pnl
        else None,
        "windows_ev_improved": sum(
            1 for label in before_metrics
            if after_metrics[label]["expected_value_score"] > before_metrics[label]["expected_value_score"]
        ),
        "windows_ev_regressed": sum(
            1 for label in before_metrics
            if after_metrics[label]["expected_value_score"] < before_metrics[label]["expected_value_score"]
        ),
        "windows_pnl_improved": sum(
            1 for label in before_metrics
            if after_metrics[label]["total_pnl"] > before_metrics[label]["total_pnl"]
        ),
        "windows_pnl_regressed": sum(
            1 for label in before_metrics
            if after_metrics[label]["total_pnl"] < before_metrics[label]["total_pnl"]
        ),
        "max_drawdown_delta_max": max(
            by_window[label]["max_drawdown_pct"] for label in by_window
        ),
        "win_rate_delta_min": min(by_window[label]["win_rate"] for label in by_window),
        "trade_count_delta_sum": sum(by_window[label]["trade_count"] for label in by_window),
    }


def _gate4(delta: dict[str, Any]) -> dict[str, Any]:
    ev_pct = delta.get("aggregate_ev_delta_pct")
    pnl_pct = delta.get("aggregate_pnl_delta_pct")
    gate_pass = (
        delta["windows_ev_improved"] >= 2
        and delta["windows_ev_regressed"] == 0
        and (
            (ev_pct is not None and ev_pct > 0.10)
            or (pnl_pct is not None and pnl_pct > 0.05)
            or delta["max_drawdown_delta_max"] < -0.01
            or (
                delta["trade_count_delta_sum"] > 0
                and delta["win_rate_delta_min"] >= 0
            )
        )
    )
    return {
        "passed": bool(gate_pass),
        "basis": (
            "Passed: majority-window EV improvement plus a Gate 4 magnitude criterion."
            if gate_pass
            else "Rejected: did not improve EV in a majority of windows with required Gate 4 magnitude."
        ),
    }


def main() -> int:
    universe = sorted(get_universe())
    baseline_config = {"ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": False}
    variant_config = {"ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH": True}

    baseline = {
        label: _run_window(universe, window, baseline_config)
        for label, window in WINDOWS.items()
    }
    variant = {
        label: _run_window(universe, window, variant_config)
        for label, window in WINDOWS.items()
    }

    before_metrics = {
        label: baseline[label]["metrics"]
        for label in WINDOWS
    }
    after_metrics = {
        label: variant[label]["metrics"]
        for label in WINDOWS
    }
    delta = _aggregate_delta(before_metrics, after_metrics)
    gate4 = _gate4(delta)
    decision = "accepted" if gate4["passed"] else "rejected"
    timestamp = datetime.now(timezone.utc).isoformat()

    log_payload = {
        "experiment_id": EXP_ID,
        "timestamp": timestamp,
        "status": decision,
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "capital_allocation_addon_quality_gate",
        "alpha_hypothesis_category": "followthrough_addon_path_quality",
        "hypothesis": (
            "Day-2 follow-through add-ons should only fire when both unrealized "
            "return and RS vs SPY continue improving from day 1 to day 2, because "
            "flat/fading follow-through may be a lower-quality add-on path."
        ),
        "why_not_llm_soft_ranking": (
            "LLM soft-ranking remains blocked by sparse production-aligned outcome joins; "
            "this tests a deterministic lifecycle alpha with fields available in OHLCV replay."
        ),
        "mechanism_insight_check": {
            "near_repeat": "partial",
            "not_repeated": [
                "not ADDON_MIN_UNREALIZED_PCT threshold tightening",
                "not ADDON_MIN_RS_VS_SPY threshold tightening",
                "not close-location threshold retry",
                "not add-on cap lift",
                "not second add-on retry",
            ],
            "why_this_is_not_simple_repeat": (
                "This uses path improvement from day 1 to day 2 as a binary quality "
                "discriminator. Prior rejected tests tuned absolute trigger thresholds, "
                "close-location thresholds, or cap room."
            ),
        },
        "parameters": {
            "single_causal_variable": "ADDON_REQUIRE_IMPROVING_FOLLOWTHROUGH",
            "old_value": False,
            "tested_value": True,
            "locked_variables": [
                "universe",
                "entry rules",
                "exit rules",
                "candidate ranking",
                "initial risk multipliers",
                "initial position caps",
                "ADDON_CHECKPOINT_DAYS=2",
                "ADDON_MIN_UNREALIZED_PCT=0.02",
                "ADDON_MIN_RS_VS_SPY=0.0",
                "ADDON_FRACTION_OF_ORIGINAL_SHARES=0.50",
                "ADDON_MAX_POSITION_PCT=0.35",
                "ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT=0.60",
                "second add-on disabled",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "primary": "2025-10-23 -> 2026-04-21",
            "secondary": [
                "2025-04-23 -> 2025-10-22",
                "2024-10-02 -> 2025-04-22",
            ],
        },
        "snapshots": {
            label: window["snapshot"]
            for label, window in WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"]
            for label, window in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": delta,
        "gate4_result": gate4,
        "addon_attribution": {
            "baseline": {
                label: baseline[label]["addon_attribution"]
                for label in WINDOWS
            },
            "variant": {
                label: variant[label]["addon_attribution"]
                for label in WINDOWS
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "notes": (
                "Rejected probes remain script-only. If accepted, mirror the "
                "improving-followthrough gate in production_parity.py before promotion."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": None if gate4["passed"] else gate4["basis"],
        "next_retry_requires": [
            "Do not retry nearby add-on path gates without event/news evidence or forward-observed add-on failure attribution.",
            "If this path-quality gate passes in future, add production parity before changing constants.",
            "Avoid cap-only add-on experiments unless affected_addon_count is non-zero before replay.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            "quant/experiments/exp_20260504_031_addon_improving_followthrough.py",
        ],
    }
    artifact = {
        "experiment_id": EXP_ID,
        "baseline_config": baseline_config,
        "variant_config": variant_config,
        "windows": WINDOWS,
        "baseline": baseline,
        "variant": variant,
        "log": log_payload,
    }
    ticket = {
        "experiment_id": EXP_ID,
        "title": "Day-2 add-on path-quality gate",
        "status": decision,
        "summary": gate4["basis"],
        "next_action": (
            "Promote with production parity if accepted; otherwise do not retry without new evidence."
        ),
        "log": str(LOG_JSON.relative_to(REPO_ROOT)),
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOG_JSON.write_text(json.dumps(log_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(log_payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
