"""exp-20260520-019: CIEN-only core promotion scout.

Archives the three-window candidate-pool experiment that temporarily added
CIEN to the shared core watchlist. The strategy change was rolled back because
the positive aggregate result depended on only one executed CIEN trade.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260520-019"
STEM = "cien_core_promotion"
DATA_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
LOG_DIR = ROOT / "experiments" / "logs"
TICKET_DIR = ROOT / "experiments" / "tickets"
ARTIFACT_DIR = ROOT / "experiments" / "artifacts"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
BASELINE_ARTIFACT = (
    ROOT / "data" / "experiments" / "exp-20260517-009" / "ample_slot_stock_rank1_topup.json"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/experiments/exp-20260520-019/ohlcv/exp-20260520-019_late_strong_cien_only_core_promotion_ohlcv.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/experiments/exp-20260520-019/ohlcv/exp-20260520-019_mid_weak_cien_only_core_promotion_ohlcv.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/experiments/exp-20260520-019/ohlcv/exp-20260520-019_old_thin_cien_only_core_promotion_ohlcv.json",
    },
}

METRIC_KEYS = (
    "expected_value_score",
    "total_pnl",
    "total_return_pct",
    "sharpe_daily",
    "max_drawdown_pct",
    "win_rate",
    "total_trades",
    "survival_rate",
    "signals_generated",
    "signals_survived",
    "worst_trade_pct",
    "max_consecutive_losses",
    "tail_loss_share",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _metric_row(result: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key in METRIC_KEYS:
        source_key = key
        output_key = "trade_count" if key == "total_trades" else key
        row[output_key] = result.get(source_key)
    return row


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = set(after) | set(before)
    out: dict[str, Any] = {}
    for key in sorted(keys):
        a = after.get(key)
        b = before.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out[key] = round(float(a) - float(b), 6)
    return out


def _aggregate(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": round(
            sum(float(row["expected_value_score"]) for row in rows.values()), 6
        ),
        "total_pnl_sum": round(sum(float(row["total_pnl"]) for row in rows.values()), 2),
        "trade_count_sum": sum(int(row["trade_count"]) for row in rows.values()),
        "min_survival_rate": min(float(row["survival_rate"]) for row in rows.values()),
        "max_drawdown_pct_max": max(float(row["max_drawdown_pct"]) for row in rows.values()),
    }


def _cien_trade_stats(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    total_count = 0
    total_pnl = 0.0
    for label, result in results.items():
        trades = [trade for trade in result.get("trades", []) if trade.get("ticker") == "CIEN"]
        pnl = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
        by_window[label] = {
            "trade_count": len(trades),
            "total_pnl": pnl,
            "trades": trades,
        }
        total_count += len(trades)
        total_pnl += pnl
    return {
        "total_trade_count": total_count,
        "total_pnl": round(total_pnl, 2),
        "by_window": by_window,
    }


def _append_jsonl_for_experiment(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    baseline = _read_json(BASELINE_ARTIFACT)["after_metrics"]
    results = {
        label: _read_json(DATA_DIR / f"{label}_backtest_results.json")
        for label in WINDOWS
    }
    before_metrics = {
        label: {
            "expected_value_score": row["expected_value_score"],
            "total_pnl": row["total_pnl"],
            "total_return_pct": row["total_return_pct"],
            "sharpe_daily": row["sharpe_daily"],
            "max_drawdown_pct": row["max_drawdown_pct"],
            "win_rate": row["win_rate"],
            "trade_count": row["trade_count"],
            "survival_rate": row["survival_rate"],
            "signals_generated": row["signals_generated"],
            "signals_survived": row["signals_survived"],
            "worst_trade_pct": row["worst_trade_pct"],
            "max_consecutive_losses": row["max_consecutive_losses"],
            "tail_loss_share": row["tail_loss_share"],
        }
        for label, row in baseline.items()
    }
    after_metrics = {label: _metric_row(result) for label, result in results.items()}
    by_window_delta = {
        label: _delta(after_metrics[label], before_metrics[label])
        for label in WINDOWS
    }
    before_aggregate = _aggregate(before_metrics)
    after_aggregate = _aggregate(after_metrics)
    aggregate_delta = _delta(after_aggregate, before_aggregate)
    cien_stats = _cien_trade_stats(results)
    gate4_passed = False
    completed_at = datetime.now(timezone.utc).isoformat()
    record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": completed_at,
        "status": "rejected_rolled_back",
        "lane": "alpha_search",
        "hypothesis": (
            "CIEN may be the narrowest viable broad-market leadership ticker promotion after "
            "the six-name core promotion batch failed; adding only CIEN to the shared core "
            "watchlist could improve replacement value without adding broad ticker noise."
        ),
        "change_summary": (
            "Temporarily added CIEN to quant/filter.py _BASE_WATCHLIST and replayed the "
            "three canonical fixed windows using CIEN-only augmented OHLCV snapshots. "
            "The watchlist change was rolled back after Gate 4 sample-quality review."
        ),
        "change_type": "candidate_pool",
        "component": "quant/filter.py",
        "changed_variable": "core_watchlist_membership_cien",
        "parameters": {
            "added_ticker": "CIEN",
            "source_prior": "exp-20260520-007 rejected six-name broad-market core promotion; retry condition allowed narrower one-ticker evidence.",
            "locked_variables": [
                "core signal rules",
                "core ranking",
                "core sizing",
                "core exits",
                "portfolio heat",
                "LLM/news replay settings",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "backtest_protocol": "docs/backtesting.md fixed three-window replay",
        "date_range": {
            label: {"start": spec["start"], "end": spec["end"], "snapshot": spec["snapshot"]}
            for label, spec in WINDOWS.items()
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": by_window_delta,
            "aggregate_before": before_aggregate,
            "aggregate_after": after_aggregate,
            "aggregate_delta": aggregate_delta,
            "candidate_trade_stats": cien_stats,
        },
        "expected_value_score_delta": aggregate_delta["expected_value_score_sum"],
        "total_pnl_delta": aggregate_delta["total_pnl_sum"],
        "gate1": {
            "baseline_artifact": str(BASELINE_ARTIFACT.relative_to(ROOT)),
            "baseline_aggregate": before_aggregate,
            "passed": True,
        },
        "gate2": {
            "required_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "OHLCV rows for CIEN in all three snapshots",
            ],
            "snapshot_manifest": str((DATA_DIR / "cien_only_ohlcv_snapshot_build.json").relative_to(ROOT)),
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "minimum_after_survival_rate": after_aggregate["min_survival_rate"],
            "passed": after_aggregate["min_survival_rate"] >= 0.05,
        },
        "gate4": {
            "passed": gate4_passed,
            "aggregate_ev_delta_positive": aggregate_delta["expected_value_score_sum"] > 0,
            "aggregate_pnl_delta_positive": aggregate_delta["total_pnl_sum"] > 0,
            "ev_regressed_windows": [
                label for label, row in by_window_delta.items() if row["expected_value_score"] < 0
            ],
            "candidate_trade_count": cien_stats["total_trade_count"],
            "candidate_trade_count_min_for_live_core_promotion": 3,
            "rejection_trigger": "only_one_executed_cien_trade",
        },
        "decision": "rejected_rolled_back",
        "rejection_reason": (
            "Aggregate EV and PnL improved, but the direct live core promotion depended on "
            "only one executed CIEN trade across the primary fixed windows. That is not "
            "enough candidate-specific evidence for a production watchlist addition."
        ),
        "next_retry_requires": [
            "Forward closed CIEN paper outcomes under core-like rules",
            "Replacement-value evidence versus displaced core candidates",
            "A governed default-off paper/pilot path before any live core promotion",
        ],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "rolled_back": True,
            "notes": "quant/filter.py was restored; no live/default orders or production watchlist changed.",
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited, nearby state-surface and broad-market "
            "scalar/profile retunes are under anti-repeat guidance, and six-name direct core "
            "promotion already failed. CIEN-only was the narrow candidate-pool test unlocked by "
            "the prior rejection."
        ),
        "related_files": [
            "quant/experiments/exp_20260520_019_cien_core_promotion.py",
            "data/experiments/exp-20260520-019/cien_core_promotion_summary.json",
            "data/experiments/exp-20260520-019/late_strong_backtest_results.json",
            "data/experiments/exp-20260520-019/mid_weak_backtest_results.json",
            "data/experiments/exp-20260520-019/old_thin_backtest_results.json",
            "experiments/logs/exp-20260520-019.json",
            "experiments/tickets/exp-20260520-019.json",
            "experiments/artifacts/exp-20260520-019_cien_core_promotion.md",
            "docs/experiment_log.jsonl",
        ],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "completed_at": completed_at,
        "record": record,
        "results": {
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "by_window_delta": by_window_delta,
            "aggregate_before": before_aggregate,
            "aggregate_after": after_aggregate,
            "aggregate_delta": aggregate_delta,
            "candidate_trade_stats": cien_stats,
        },
    }


def artifact_markdown(payload: dict[str, Any]) -> str:
    record = payload["record"]
    results = payload["results"]
    lines = [
        f"# {EXPERIMENT_ID} CIEN-only core promotion scout",
        "",
        "## Hypothesis",
        record["hypothesis"],
        "",
        "## Gate 1 Baseline",
        f"- baseline artifact: `{record['gate1']['baseline_artifact']}`",
        f"- aggregate EV before: `{results['aggregate_before']['expected_value_score_sum']}`",
        f"- aggregate PnL before: `{results['aggregate_before']['total_pnl_sum']}`",
        "",
        "## Gate 2 Field Check",
        f"- snapshot manifest: `{record['gate2']['snapshot_manifest']}`",
        "- CIEN OHLCV is present in all three augmented snapshots.",
        "",
        "## Gate 3 Survival",
        f"- min survival after: `{record['gate3']['minimum_after_survival_rate']}`",
        "- no new filter was added.",
        "",
        "## Gate 4 Three-Window Result",
        "| window | EV before | EV after | EV delta | PnL delta | DD delta | trades before | trades after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = results["before_metrics"][label]
        after = results["after_metrics"][label]
        delta = results["by_window_delta"][label]
        lines.append(
            "| {label} | {ev_before:.4f} | {ev_after:.4f} | {ev_delta:.4f} | {pnl_delta:.2f} | {dd_delta:.4f} | {trades_before} | {trades_after} |".format(
                label=label,
                ev_before=before["expected_value_score"],
                ev_after=after["expected_value_score"],
                ev_delta=delta["expected_value_score"],
                pnl_delta=delta["total_pnl"],
                dd_delta=delta["max_drawdown_pct"],
                trades_before=before["trade_count"],
                trades_after=after["trade_count"],
            )
        )
    lines.extend(
        [
            "",
            "## Candidate Trade Breadth",
            f"- CIEN primary-window trades: `{results['candidate_trade_stats']['total_trade_count']}`",
            f"- CIEN primary-window PnL: `{results['candidate_trade_stats']['total_pnl']}`",
            "",
            "## Decision",
            f"- decision: `{record['decision']}`",
            f"- aggregate EV delta: `{record['expected_value_score_delta']}`",
            f"- aggregate PnL delta: `{record['total_pnl_delta']}`",
            f"- rejection reason: {record['rejection_reason']}",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            "  shared_policy_changed: false",
            "  backtester_adapter_changed: false",
            "  run_adapter_changed: false",
            "  replay_only: true",
            "  parity_test_added: false",
            "  rolled_back: true",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def persist(payload: dict[str, Any]) -> None:
    _write_json(DATA_DIR / f"{STEM}_summary.json", payload)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", payload["record"])
    _write_json(
        TICKET_DIR / f"{EXPERIMENT_ID}.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["record"]["decision"],
            "summary": "CIEN-only core promotion positive but rejected for one-trade evidence.",
            "artifact": str((ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md").relative_to(ROOT)),
            "json": str((DATA_DIR / f"{STEM}_summary.json").relative_to(ROOT)),
        },
    )
    artifact_path = ARTIFACT_DIR / f"{EXPERIMENT_ID}_{STEM}.md"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_experiment(EXPERIMENT_LOG, payload["record"])


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["record"]["decision"],
                "aggregate_ev_delta": payload["record"]["expected_value_score_delta"],
                "aggregate_pnl_delta": payload["record"]["total_pnl_delta"],
                "cien_trade_count": payload["results"]["candidate_trade_stats"]["total_trade_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
