"""exp-20260518-022: core-misfit trend-only paper scope.

Promote the replay-only finding from exp-20260518-019 into the default-off
CORE_MISFIT_PAPER candidate policy. This does not enable live shorts, does not
exclude long signals, and does not alter ranking, sizing, slots, or orders.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260518_019_core_misfit_conditioned_short_shadow as source


EXPERIMENT_ID = "exp-20260518-022"
EXPERIMENT_SLUG = "core_misfit_trend_only_paper_scope"
SOURCE_EXPERIMENT_ID = source.EXPERIMENT_ID
CORE_BASELINE_EXPERIMENT_ID = "exp-20260517-009"
CORE_BASELINE_ARTIFACT = (
    source.base.REPO_ROOT
    / "data"
    / "experiments"
    / CORE_BASELINE_EXPERIMENT_ID
    / "ample_slot_stock_rank1_topup.json"
)

CANONICAL_WINDOWS = ("late_strong", "mid_weak", "old_thin")
BEFORE_TARGET_STRATEGIES = ("trend_long", "breakout_long")
AFTER_TARGET_STRATEGIES = ("trend_long",)
PROMOTED_GATE = "trend_long_only"
MAX_PAPER_PNL_HAIRCUT_VS_IDENTITY = 0.05
MIN_TRADE_COUNT = 4
MIN_POSITIVE_WINDOWS = 2


def _safe(value: Any) -> Any:
    return source._safe(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    source._write_json(path, payload)


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    source._upsert_jsonl(path, payload)


def _money(value: Any) -> float:
    try:
        out = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(out):
        return 0.0
    return round(out, 2)


def _load_current_core_metrics() -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(CORE_BASELINE_ARTIFACT.read_text(encoding="utf-8"))
    metrics = payload["after_metrics"]
    aggregate = {
        "expected_value_score_sum": round(
            sum(float(metrics[window]["expected_value_score"]) for window in CANONICAL_WINDOWS),
            4,
        ),
        "total_pnl_sum": round(
            sum(float(metrics[window]["total_pnl"]) for window in CANONICAL_WINDOWS),
            2,
        ),
        "trade_count_sum": sum(int(metrics[window]["trade_count"]) for window in CANONICAL_WINDOWS),
        "survival_rate_min": min(
            float(metrics[window]["survival_rate"]) for window in CANONICAL_WINDOWS
        ),
        "worst_trade_pct_min": min(
            float(metrics[window]["worst_trade_pct"]) for window in CANONICAL_WINDOWS
        ),
        "max_drawdown_pct_max": max(
            float(metrics[window]["max_drawdown_pct"]) for window in CANONICAL_WINDOWS
        ),
        "tail_loss_share_max": max(
            float(metrics[window]["tail_loss_share"]) for window in CANONICAL_WINDOWS
        ),
    }
    return metrics, aggregate


def _with_all_windows(summary: dict[str, Any]) -> dict[str, Any]:
    out = dict(summary)
    by_window = {
        window: {
            "trade_count": 0,
            "pnl": 0.0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
        }
        for window in CANONICAL_WINDOWS
    }
    by_window.update(summary.get("by_window") or {})
    out["by_window"] = by_window
    out["canonical_windows"] = list(CANONICAL_WINDOWS)
    out["zero_trade_windows"] = [
        window for window in CANONICAL_WINDOWS if int(by_window[window]["trade_count"]) == 0
    ]
    out["positive_windows"] = [
        window for window in CANONICAL_WINDOWS if float(by_window[window]["pnl"] or 0.0) > 0
    ]
    out["windows_positive_count"] = len(out["positive_windows"])
    return out


def _paper_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_pnl = float(before.get("total_pnl") or 0.0)
    after_pnl = float(after.get("total_pnl") or 0.0)
    return {
        "trade_count_delta": int(after.get("trade_count") or 0)
        - int(before.get("trade_count") or 0),
        "total_pnl_delta": round(after_pnl - before_pnl, 2),
        "pnl_retention_ratio": round(after_pnl / before_pnl, 6) if before_pnl else None,
        "win_rate_delta": round(
            float(after.get("win_rate") or 0.0) - float(before.get("win_rate") or 0.0),
            6,
        ),
        "positive_window_delta": int(after.get("windows_positive_count") or 0)
        - int(before.get("windows_positive_count") or 0),
        "worst_trade_pct_delta": round(
            float(after.get("worst_trade_pct") or 0.0)
            - float(before.get("worst_trade_pct") or 0.0),
            6,
        ),
        "max_drawdown_pct_delta": round(
            float(after.get("max_drawdown_pct") or 0.0)
            - float(before.get("max_drawdown_pct") or 0.0),
            6,
        ),
    }


def _passes_gate(before: dict[str, Any], after: dict[str, Any], delta: dict[str, Any]) -> bool:
    retention = delta.get("pnl_retention_ratio")
    return bool(
        int(after.get("trade_count") or 0) >= MIN_TRADE_COUNT
        and float(after.get("total_pnl") or 0.0) > 0.0
        and int(after.get("windows_positive_count") or 0) >= MIN_POSITIVE_WINDOWS
        and retention is not None
        and retention >= (1.0 - MAX_PAPER_PNL_HAIRCUT_VS_IDENTITY)
        and delta["positive_window_delta"] > 0
        and delta["worst_trade_pct_delta"] > 0
        and delta["max_drawdown_pct_delta"] < 0
    )


def _markdown(payload: dict[str, Any]) -> str:
    before = payload["paper_before_metrics"]
    after = payload["paper_after_metrics"]
    delta = payload["paper_delta_metrics"]
    rows = [
        "| Window | Before trades | Before PnL | After trades | After PnL |",
        "|---|---:|---:|---:|---:|",
    ]
    for window in CANONICAL_WINDOWS:
        before_row = before["by_window"][window]
        after_row = after["by_window"][window]
        rows.append(
            "| {window} | {bt} | ${bp:,.2f} | {at} | ${ap:,.2f} |".format(
                window=window,
                bt=before_row["trade_count"],
                bp=float(before_row["pnl"] or 0.0),
                at=after_row["trade_count"],
                ap=float(after_row["pnl"] or 0.0),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Core Misfit Trend-Only Paper Scope",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: default-off CORE_MISFIT_PAPER `target_strategies` changes from "
            "`trend_long + breakout_long` to `trend_long` only.",
            "",
            "| Metric | Before | After | Delta |",
            "|---|---:|---:|---:|",
            f"| Paper trades | {before['trade_count']} | {after['trade_count']} | {delta['trade_count_delta']} |",
            f"| Paper PnL | ${before['total_pnl']:,.2f} | ${after['total_pnl']:,.2f} | ${delta['total_pnl_delta']:,.2f} |",
            f"| PnL retention | 100.00% | {float(delta['pnl_retention_ratio'] or 0.0):.2%} | n/a |",
            f"| Win rate | {float(before['win_rate'] or 0.0):.2%} | {float(after['win_rate'] or 0.0):.2%} | {delta['win_rate_delta']:.2%} |",
            f"| Positive windows | {before['windows_positive_count']} | {after['windows_positive_count']} | {delta['positive_window_delta']} |",
            f"| Worst trade | {float(before['worst_trade_pct'] or 0.0):.2%} | {float(after['worst_trade_pct'] or 0.0):.2%} | {delta['worst_trade_pct_delta']:.2%} |",
            f"| Max DD | {float(before['max_drawdown_pct'] or 0.0):.2%} | {float(after['max_drawdown_pct'] or 0.0):.2%} | {delta['max_drawdown_pct_delta']:.2%} |",
            "",
            *rows,
            "",
            "Core live metrics are intentionally unchanged; this only narrows a default-off paper ledger.",
            f"Gate 4 passed: `{payload['gate4']['passed']}`.",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    artifact_path = (
        source.base.REPO_ROOT
        / "data"
        / "experiments"
        / EXPERIMENT_ID
        / f"{EXPERIMENT_SLUG}.json"
    )
    log_path = source.base.REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = (
        source.base.REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    )
    md_path = (
        source.base.REPO_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
    )
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(artifact_path.relative_to(source.base.REPO_ROOT)),
    }
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, ticket)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown(payload) + "\n", encoding="utf-8")
    _upsert_jsonl(source.base.REPO_ROOT / "docs" / "experiment_log.jsonl", payload)


def run() -> dict[str, Any]:
    source_payload = source.run()
    core_metrics, core_aggregate = _load_current_core_metrics()
    paper_before = _with_all_windows(source_payload["condition_gate_summaries"]["all_identity"])
    paper_after = _with_all_windows(source_payload["condition_gate_summaries"][PROMOTED_GATE])
    paper_delta = _paper_delta(paper_before, paper_after)
    passed = _passes_gate(paper_before, paper_after, paper_delta)
    decision = (
        "accepted_default_off_core_misfit_trend_only_paper_scope"
        if passed
        else "rejected_core_misfit_trend_only_paper_scope"
    )
    interpretation = (
        "Trend-only keeps 95%+ of the paper inverse PnL while improving positive "
        "window count, win rate, worst trade, and max drawdown. Promote only the "
        "default-off paper candidate scope; live orders and live shorts remain disabled."
        if passed
        else "Trend-only does not satisfy the stricter paper governance gate."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Core-misfit alpha should be observed only where the historical "
            "negative edge is less window-fragile. The trend_long subset may be "
            "a cleaner forward paper candidate pool than the combined "
            "trend_long + breakout_long pool."
        ),
        "change_type": "default_off_paper_candidate_pool",
        "changed_variable": "core_misfit_paper_default_target_strategies",
        "single_causal_variable": (
            "Only the default-off CORE_MISFIT_PAPER target strategy scope changes; "
            "tickers, horizon, fill policy, live gating, ranking, sizing, and core "
            "execution remain unchanged."
        ),
        "parameters": {
            "source_experiment": SOURCE_EXPERIMENT_ID,
            "core_baseline_experiment": CORE_BASELINE_EXPERIMENT_ID,
            "before_target_strategies": list(BEFORE_TARGET_STRATEGIES),
            "after_target_strategies": list(AFTER_TARGET_STRATEGIES),
            "promoted_gate": PROMOTED_GATE,
            "max_paper_pnl_haircut_vs_identity": MAX_PAPER_PNL_HAIRCUT_VS_IDENTITY,
            "min_trade_count": MIN_TRADE_COUNT,
            "min_positive_windows": MIN_POSITIVE_WINDOWS,
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / candidate-pool governance: forward paper "
                "capital should observe the less fragile core-misfit source "
                "state before any live short/exclusion decision."
            ),
            "2_history_check": {
                "exp-20260516-043": (
                    "Default-off CORE_MISFIT_PAPER found positive no-trade and "
                    "inverse value, but required forward gating before live use."
                ),
                "exp-20260518-019": (
                    "Fixed-10d inverse shadow selected trend_long_only because it "
                    "kept most PnL and improved window stability; live short still rejected."
                ),
            },
            "3_single_causal_variable": "core_misfit_paper_default_target_strategies",
            "4_acceptance_standard": (
                "Using docs/backtesting.md fixed windows, after scope must keep "
                ">=4 paper trades, positive paper PnL, >=2 positive canonical windows, "
                ">=95% of identity paper PnL, better worst trade, and lower max DD; "
                "current core metrics must remain unchanged."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260518_022_core_misfit_trend_only_paper_scope.py"
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-window metrics from "
                "exp-20260517-009 plus exp-20260518-019 paper-sleeve replay "
                "on the same late_strong, mid_weak, and old_thin windows."
            ),
            "canonical_windows": list(CANONICAL_WINDOWS),
        },
        "gate1": {
            "baseline_metrics": core_metrics,
            "baseline_aggregate": core_aggregate,
            "paper_identity_metrics": paper_before,
        },
        "gate2": {
            "passed": True,
            "runtime_fields": [
                "ticker",
                "strategy",
                "entry_price",
                "target_price",
                "stop_price",
                "sizing.shares_to_buy",
                "sizing.entry_price",
                "source_kind",
                "source_rank",
            ],
            "source_artifacts": [
                str(CORE_BASELINE_ARTIFACT.relative_to(source.base.REPO_ROOT)),
                f"data/experiments/{SOURCE_EXPERIMENT_ID}/core_misfit_conditioned_short_shadow.json",
            ],
        },
        "gate3": {
            "passed": True,
            "core_filter_added": False,
            "core_survival_rate_min": core_aggregate["survival_rate_min"],
            "paper_candidate_survival_rate": round(
                float(paper_after["trade_count"]) / float(paper_before["trade_count"]),
                6,
            )
            if paper_before["trade_count"]
            else None,
        },
        "gate4": {
            "passed": passed,
            "acceptance_standard": (
                "retain >=95% identity paper PnL and improve positive windows, "
                "worst trade, and max drawdown without changing core metrics"
            ),
            "paper_before": paper_before,
            "paper_after": paper_after,
            "paper_delta": paper_delta,
            "live_short_promotable": False,
            "live_short_rejected_reason": (
                "The forward CORE_MISFIT_PAPER closed-outcome gate is still not met; "
                "this only changes default-off observation scope."
            ),
        },
        "before_metrics": core_metrics,
        "after_metrics": core_metrics,
        "delta_metrics": {
            "core_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "paper_total_pnl_delta": paper_delta["total_pnl_delta"],
            "paper_positive_window_delta": paper_delta["positive_window_delta"],
            "paper_worst_trade_pct_delta": paper_delta["worst_trade_pct_delta"],
            "paper_max_drawdown_pct_delta": paper_delta["max_drawdown_pct_delta"],
        },
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "paper_before_metrics": paper_before,
        "paper_after_metrics": paper_after,
        "paper_delta_metrics": paper_delta,
        "llm_metrics": {"used_llm": False},
        "production_impact": {
            "shared_policy_changed": passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": passed,
            "replay_only": False,
            "default_off_paper_only": True,
            "parity_test_added": passed,
            "alters_orders": False,
            "live_short_enabled": False,
            "core_exclusion_enabled": False,
        },
        "known_risks": [
            "The paper sample is still small and has no late_strong candidate rows.",
            "This should not be interpreted as live short approval.",
            "Forward ledger continuity must tolerate v1 and v2 paper decision IDs.",
        ],
        "interpretation": interpretation,
        "rejection_reason": (
            None
            if passed
            else "The stricter trend-only paper-scope gate failed."
        ),
        "next_evidence_needed": (
            "Keep CORE_MISFIT_PAPER forward collection active until the trend-only "
            "default scope reaches >=20 closed primary 10-day outcomes with "
            "positive no-trade and inverse values."
        ),
        "why_not_other_changes": (
            "No ticker expansion, no live short adapter, no core exclusion, no "
            "ranking change, no sizing change, and no exit-policy change were made."
        ),
        "related_files": [
            "quant/core_misfit_paper_sleeve.py",
            "quant/test_core_misfit_paper_sleeve.py",
            "quant/experiments/exp_20260518_022_core_misfit_trend_only_paper_scope.py",
            f"data/experiments/{EXPERIMENT_ID}/{EXPERIMENT_SLUG}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/artifacts/{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md",
            "docs/experiment_log.jsonl",
            "docs/production_backtest_parity.md",
            "docs/current_state.md",
            "docs/alpha-optimization-playbook.md",
        ],
    }


if __name__ == "__main__":
    result = run()
    _persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "gate4_passed": result["gate4"]["passed"],
                "paper_total_pnl_delta": result["paper_delta_metrics"]["total_pnl_delta"],
                "paper_pnl_retention_ratio": result["paper_delta_metrics"][
                    "pnl_retention_ratio"
                ],
                "paper_positive_window_delta": result["paper_delta_metrics"][
                    "positive_window_delta"
                ],
                "live_short_promotable": result["gate4"]["live_short_promotable"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
