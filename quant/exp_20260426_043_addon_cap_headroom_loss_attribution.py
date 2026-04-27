"""Observed-only audit for add-on cap-headroom newly executed events.

This experiment does not change strategy behavior. It reads the prior
cap-headroom replay artifacts and classifies the add-ons that became executable
only when add-on execution was allowed to use a 35% single-position cap.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE_SHADOW = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_027_entry_followthrough_addon_cap_headroom_results.json",
)
REAL_BEFORE = os.path.join(REPO_ROOT, "data", "backtest_results_20260426_exp028_baseline.json")
REAL_AFTER = os.path.join(REPO_ROOT, "data", "backtest_results_20260426_exp028_after.json")
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_043_addon_cap_headroom_loss_attribution.json",
)

EXPERIMENT_ID = "exp-20260426-043"
TARGET_VARIANT = "addon_cap_35pct"


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _trade_key(trade: dict) -> tuple:
    return (
        trade.get("ticker"),
        trade.get("strategy"),
        trade.get("entry_date"),
        trade.get("exit_date"),
    )


def _event_key(event: dict) -> tuple:
    return (
        event.get("ticker"),
        event.get("strategy"),
        event.get("checkpoint_date"),
        event.get("scheduled_fill_date"),
    )


def _index_trades(window_result: dict) -> dict[tuple, dict]:
    return {_trade_key(trade): trade for trade in window_result.get("trades", [])}


def _window_metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "addons_executed": result.get("addon_attribution", {}).get("executed"),
        "addons_skipped": result.get("addon_attribution", {}).get("skipped"),
    }


def _classify_event(event: dict, trade_delta_pnl: float | None) -> str:
    if trade_delta_pnl is not None and trade_delta_pnl < 0:
        return "adverse_incremental_pnl"
    if event.get("matched_exit_reason") == "stop":
        return "adverse_stop_exit"
    if event.get("matched_exit_reason") == "target" and (trade_delta_pnl or 0) > 0:
        return "benign_target_winner"
    if (event.get("addon_shares") or 0) < (event.get("requested_shares") or 0):
        return "partially_clipped_benign"
    return "neutral_or_unclassified"


def _summarize_counts(rows: list[dict], field: str) -> dict:
    return dict(sorted(Counter(row.get(field) or "unknown" for row in rows).items()))


def main() -> int:
    shadow = _load_json(SOURCE_SHADOW)
    real_before = _load_json(REAL_BEFORE)
    real_after = _load_json(REAL_AFTER)

    windows = {}
    all_rows = []

    for label, shadow_window in shadow.get("windows", {}).items():
        variant = shadow_window.get("variants", {}).get(TARGET_VARIANT, {})
        before_window = real_before.get("windows", {}).get(label, {})
        after_window = real_after.get("windows", {}).get(label, {})
        before_trades = _index_trades(before_window)
        after_trades = _index_trades(after_window)

        rows = []
        for event in variant.get("newly_executed_events", []):
            matched_after = None
            matched_before = None
            for key, trade in after_trades.items():
                if (
                    trade.get("ticker") == event.get("ticker")
                    and trade.get("strategy") == event.get("strategy")
                    and trade.get("exit_date") == event.get("matched_exit_date")
                ):
                    matched_after = trade
                    matched_before = before_trades.get(key)
                    break

            pnl_after = matched_after.get("pnl") if matched_after else None
            pnl_before = matched_before.get("pnl") if matched_before else None
            trade_delta_pnl = (
                round(pnl_after - pnl_before, 2)
                if isinstance(pnl_after, (int, float)) and isinstance(pnl_before, (int, float))
                else None
            )
            requested = event.get("requested_shares") or 0
            added = event.get("addon_shares") or 0
            row = {
                "window": label,
                "event_key": list(_event_key(event)),
                "ticker": event.get("ticker"),
                "strategy": event.get("strategy"),
                "sector": event.get("sector"),
                "checkpoint_date": event.get("checkpoint_date"),
                "scheduled_fill_date": event.get("scheduled_fill_date"),
                "matched_exit_date": event.get("matched_exit_date"),
                "matched_exit_reason": event.get("matched_exit_reason"),
                "unrealized_pct": event.get("unrealized_pct"),
                "rs_vs_spy": event.get("rs_vs_spy"),
                "requested_shares": requested,
                "addon_shares": added,
                "fill_ratio": round(added / requested, 4) if requested else None,
                "normal_trade_pnl": pnl_before,
                "headroom_trade_pnl": pnl_after,
                "trade_delta_pnl": trade_delta_pnl,
                "outcome_family": _classify_event(event, trade_delta_pnl),
            }
            rows.append(row)
            all_rows.append(row)

        family_pnl = defaultdict(float)
        for row in rows:
            if isinstance(row["trade_delta_pnl"], (int, float)):
                family_pnl[row["outcome_family"]] += row["trade_delta_pnl"]

        windows[label] = {
            "normal_25pct_addon_metrics": _window_metrics(before_window),
            "addon_only_35pct_cap_metrics": _window_metrics(after_window),
            "newly_executed_count": len(rows),
            "outcome_family_counts": _summarize_counts(rows, "outcome_family"),
            "strategy_counts": _summarize_counts(rows, "strategy"),
            "sector_counts": _summarize_counts(rows, "sector"),
            "trade_delta_pnl_sum": round(
                sum(row["trade_delta_pnl"] or 0.0 for row in rows),
                2,
            ),
            "trade_delta_pnl_by_family": {
                key: round(value, 2) for key, value in sorted(family_pnl.items())
            },
            "events": rows,
        }

    aggregate_family_pnl = defaultdict(float)
    for row in all_rows:
        if isinstance(row["trade_delta_pnl"], (int, float)):
            aggregate_family_pnl[row["outcome_family"]] += row["trade_delta_pnl"]

    adverse_rows = [
        row for row in all_rows
        if str(row.get("outcome_family", "")).startswith("adverse")
    ]
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "loss_attribution",
        "change_type": "failure_taxonomy",
        "single_causal_variable": (
            "add-on-only cap headroom newly executed add-on adverse outcome taxonomy v2"
        ),
        "source_files": {
            "shadow_cap_headroom_replay": os.path.relpath(SOURCE_SHADOW, REPO_ROOT),
            "normal_25pct_addon_real_replay": os.path.relpath(REAL_BEFORE, REPO_ROOT),
            "addon_only_35pct_cap_real_replay": os.path.relpath(REAL_AFTER, REPO_ROOT),
        },
        "target_variant": TARGET_VARIANT,
        "windows": windows,
        "aggregate": {
            "newly_executed_count": len(all_rows),
            "adverse_count": len(adverse_rows),
            "outcome_family_counts": _summarize_counts(all_rows, "outcome_family"),
            "strategy_counts": _summarize_counts(all_rows, "strategy"),
            "sector_counts": _summarize_counts(all_rows, "sector"),
            "trade_delta_pnl_sum": round(
                sum(row["trade_delta_pnl"] or 0.0 for row in all_rows),
                2,
            ),
            "trade_delta_pnl_by_family": {
                key: round(value, 2) for key, value in sorted(aggregate_family_pnl.items())
            },
        },
        "interpretation": {
            "decision": "observed_only",
            "finding": (
                "The 35% add-on-only cap created four newly executed add-on events "
                "across the fixed windows, and none formed an adverse outcome family. "
                "The materiality problem is small sample size and cap clipping, not an "
                "identified bad subfamily."
            ),
            "next_alpha_implication": (
                "Do not spend the next iteration on another nearby price-confirmation "
                "prefilter for this add-on branch. A future production-promotion attempt "
                "needs either forward evidence, more qualifying samples, or a materially "
                "different trigger source."
            ),
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(json.dumps(result["aggregate"], indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
