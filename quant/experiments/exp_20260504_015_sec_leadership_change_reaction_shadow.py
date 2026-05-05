"""Shadow alpha check for SEC leadership-change reaction drift.

This experiment intentionally does not change trading logic. It tests whether
8-K leadership-change filings with an initial negative excess reaction show a
repeatable rebound pattern across the canonical three backtest windows.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from data_layer import get_universe
from experiments.exp_20260503_051_sec_filing_reaction_drift import (
    SEC_EVENTS_PATH,
    WINDOWS,
    _compact_event,
    _load_snapshot,
    _safe_payload,
    _write_json,
    attach_slot_conflicts,
    evaluate_group,
    load_event_groups,
    run_baseline_windows,
)


EXPERIMENT_ID = "exp-20260504-015"
ARTIFACT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
LOG_DIR = ROOT / "docs" / "experiments" / "logs"
TICKET_DIR = ROOT / "docs" / "experiments" / "tickets"
AUDIT_DIR = ROOT / "docs" / "non_ohlcv_data_audit"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"

PRIMARY_REACTION_BUCKET = "negative_excess_le_minus_2pct"


def _excess(row: dict[str, Any], horizon: str) -> float | None:
    value = ((row.get("horizons") or {}).get(horizon) or {}).get("excess_return")
    return value if isinstance(value, (int, float)) else None


def _pct(value: float | None) -> float | None:
    return round(value * 100.0, 4) if isinstance(value, (int, float)) else None


def _numeric_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0}
    positives = [v for v in values if v > 0]
    return {
        "count": len(values),
        "avg_pct": _pct(mean(values)),
        "median_pct": _pct(median(values)),
        "positive_rate_pct": round(len(positives) / len(values) * 100.0, 2),
        "best_pct": _pct(max(values)),
        "worst_pct": _pct(min(values)),
    }


def _by_window(rows: list[dict[str, Any]], horizon: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = _excess(row, horizon)
        if value is not None:
            grouped[row["window"]].append(value)
    return {name: _numeric_summary(values) for name, values in sorted(grouped.items())}


def _dominance(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    valid_rows = [row for row in rows if _excess(row, horizon) is not None]
    if not valid_rows:
        return {"valid_events": 0}

    counts = Counter(row["ticker"] for row in valid_rows)
    contribution: dict[str, float] = defaultdict(float)
    for row in valid_rows:
        contribution[row["ticker"]] += _excess(row, horizon) or 0.0

    top_count_ticker, top_count = counts.most_common(1)[0]
    total_abs = sum(abs(value) for value in contribution.values())
    top_abs_share = None
    if total_abs > 0:
        top_abs_share = max(abs(value) for value in contribution.values()) / total_abs

    return {
        "valid_events": len(valid_rows),
        "unique_tickers": len(counts),
        "top_count_ticker": top_count_ticker,
        "top_count_share_pct": round(top_count / len(valid_rows) * 100.0, 2),
        "top_abs_contribution_share_pct": _pct(top_abs_share),
    }


def _branch_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: (row["usable_trade_date"], row["ticker"]))
    return {
        "event_count": len(rows),
        "unique_tickers": len({row["ticker"] for row in rows}),
        "by_window_10d": _by_window(rows, "10d"),
        "by_window_20d": _by_window(rows, "20d"),
        "forward_5d": _forward_excess_summary(rows, "5d"),
        "forward_10d": _forward_excess_summary(rows, "10d"),
        "forward_20d": _forward_excess_summary(rows, "20d"),
        "reaction_buckets": dict(Counter(row.get("reaction_bucket") for row in rows)),
        "slot_conflicts": dict(Counter(bool(row.get("slot_conflict_proxy")) for row in rows)),
        "dominance_10d": _dominance(rows, "10d"),
        "examples": [_compact_event(row) for row in rows[:8]],
    }


def _forward_excess_summary(rows: list[dict[str, Any]], horizon: str) -> dict[str, Any]:
    values = [_excess(row, horizon) for row in rows]
    values = [value for value in values if value is not None]
    summary = _numeric_summary(values)
    return {
        "count": summary.get("count", 0),
        "avg_excess_pct": summary.get("avg_pct"),
        "median_excess_pct": summary.get("median_pct"),
        "positive_rate_pct": summary.get("positive_rate_pct"),
        "best_excess_pct": summary.get("best_pct"),
        "worst_excess_pct": summary.get("worst_pct"),
    }


def _positive_window_count(rows: list[dict[str, Any]], horizon: str) -> int:
    count = 0
    for summary in _by_window(rows, horizon).values():
        avg_pct = summary.get("avg_pct")
        if isinstance(avg_pct, (int, float)) and avg_pct > 0:
            count += 1
    return count


def _rank_tickers(rows: list[dict[str, Any]], horizon: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = _excess(row, horizon)
        if value is not None:
            grouped[row["ticker"]].append(value)
    ranked = [
        {
            "ticker": ticker,
            "count": len(values),
            "avg_excess_pct": _pct(mean(values)),
            "sum_excess_pct": _pct(sum(values)),
        }
        for ticker, values in grouped.items()
    ]
    return sorted(ranked, key=lambda item: (item["sum_excess_pct"], item["count"]), reverse=True)[:12]


def _decision(primary_rows: list[dict[str, Any]]) -> tuple[str, str]:
    values_10d = [_excess(row, "10d") for row in primary_rows]
    values_10d = [value for value in values_10d if value is not None]
    if len(values_10d) < 10:
        return (
            "rejected_insufficient_sample",
            "Primary branch has fewer than 10 valid 10d observations.",
        )
    if mean(values_10d) <= 0:
        return (
            "rejected_negative_or_flat_forward_edge",
            "Primary branch average 10d excess return is not positive.",
        )
    if _positive_window_count(primary_rows, "10d") < 2:
        return (
            "rejected_not_multi_window_stable",
            "Primary branch is not positive in at least two canonical windows.",
        )
    dominance = _dominance(primary_rows, "10d")
    if (dominance.get("top_count_share_pct") or 100.0) > 50.0:
        return (
            "shadow_promising_but_concentrated",
            "Primary branch is positive but sample is concentrated in one ticker.",
        )
    return (
        "shadow_promising_not_promoted",
        "Primary branch is positive across multiple windows; keep observe-only until forward evidence exists.",
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    existing: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                existing.append(line)
                continue
            if payload.get("experiment_id") != EXPERIMENT_ID:
                existing.append(line)
    existing.append(json.dumps(_safe_payload(record), ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(existing) + "\n", encoding="utf-8")


def _write_audit(report: dict[str, Any]) -> Path:
    primary = report["branches"]["leadership_change_negative_reaction"]
    decision = report["decision"]
    valid_10d_count = primary["forward_10d"].get("count", 0)
    lines = [
        f"# {EXPERIMENT_ID} SEC Leadership-Change Reaction Shadow",
        "",
        f"- decision: `{decision['status']}`",
        f"- primary branch: `filing_category=leadership_change` + `reaction_bucket={PRIMARY_REACTION_BUCKET}`",
        f"- event rows: {primary['event_count']}",
        f"- valid 10d observations: {valid_10d_count}",
        f"- unique tickers: {primary['unique_tickers']}",
        f"- 10d avg excess: {primary['forward_10d'].get('avg_excess_pct')}%",
        f"- 10d positive windows: {_positive_window_count(report['primary_rows_for_audit'], '10d')}/3",
        f"- production impact: `{report['production_impact']['production_impact']}`",
        "",
        "## Window Summary",
        "",
        "| window | count | avg 10d excess % | positive rate % |",
        "|---|---:|---:|---:|",
    ]
    for window, summary in primary["by_window_10d"].items():
        lines.append(
            f"| {window} | {summary.get('count', 0)} | "
            f"{summary.get('avg_pct')} | {summary.get('positive_rate_pct')} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            decision["reason"],
            "",
            "This is a replay-only shadow measurement. It does not alter entries, exits, ranking, sizing, "
            "or any production trading decision.",
        ]
    )
    path = AUDIT_DIR / "sec_leadership_change_reaction_shadow_20260504.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    universe = sorted(get_universe())
    baseline_metrics, baseline_trades = run_baseline_windows(universe)
    event_groups = load_event_groups(SEC_EVENTS_PATH)
    snapshots = {
        label: _load_snapshot(ROOT / cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }

    rows: list[dict[str, Any]] = []
    for label, cfg in WINDOWS.items():
        snapshot = snapshots[label]
        spy_rows = snapshot.get("SPY") or []
        for group in event_groups:
            usable_date = group["usable_trade_date"]
            if cfg["start"] <= usable_date <= cfg["end"]:
                rows.append(evaluate_group(group, snapshot, spy_rows, label))

    covered_rows = [row for row in rows if row.get("price_status") == "covered"]
    covered_rows, slot_summary = attach_slot_conflicts(
        covered_rows,
        baseline_trades,
        snapshots,
    )
    leadership_rows = [
        row for row in covered_rows if row.get("filing_category") == "leadership_change"
    ]
    primary_rows = [
        row
        for row in leadership_rows
        if row.get("reaction_bucket") == PRIMARY_REACTION_BUCKET
    ]
    nonnegative_rows = [
        row
        for row in leadership_rows
        if row.get("reaction_bucket")
        in {"positive_excess_ge_2pct", "mild_positive_excess_0_to_2pct"}
    ]

    status, reason = _decision(primary_rows)

    production_impact = {
        "production_impact": "replay_only",
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "parity_test_added": False,
        "alters_orders": False,
        "alters_ranking": False,
        "alters_sizing": False,
        "notes": "Shadow measurement only; no production or backtest trading policy changed.",
    }

    report: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "hypothesis": (
            "SEC 8-K leadership-change filings with a strong negative initial excess reaction "
            "may capture temporary uncertainty that mean-reverts over the next 10 trading days."
        ),
        "classification": "alpha_search",
        "alpha_category": "event_source_context",
        "why_not_blocked": (
            "LLM soft-ranking remains sample-limited, so this uses existing SEC filing event data "
            "and canonical OHLCV snapshots across all fixed windows."
        ),
        "history_check": {
            "not_repeating_exp_20260503_051": (
                "That experiment rejected broad positive reaction gates. This tests a single "
                "8-K leadership-change semantic category plus a fixed negative reaction bucket."
            ),
            "not_repeating_exp_20260504_010_or_012": (
                "Those experiments focused on Item 2.02 negative language / negative reaction. "
                "This branch uses Item 5.02-style leadership-change context and no text keyword score."
            ),
            "mechanism_insight_guardrail": (
                "No threshold sweep, no nearby SPY-relative leader tuning, no LLM replay promotion."
            ),
        },
        "date_windows": WINDOWS,
        "parameters": {
            "filing_category": "leadership_change",
            "primary_reaction_bucket": PRIMARY_REACTION_BUCKET,
            "horizon_primary": "10d",
            "min_valid_10d_events": 10,
            "required_positive_windows": 2,
        },
        "baseline_metrics": baseline_metrics,
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "expected_value_score_delta": {
            name: 0.0 for name in sorted(baseline_metrics)
        },
        "branches": {
            "leadership_change_all": _branch_summary(leadership_rows),
            "leadership_change_negative_reaction": _branch_summary(primary_rows),
            "leadership_change_nonnegative_reaction": _branch_summary(nonnegative_rows),
        },
        "slot_conflict_summary": slot_summary,
        "ticker_rank_10d_primary": _rank_tickers(primary_rows, "10d"),
        "decision": {
            "status": status,
            "reason": reason,
        },
        "production_impact": production_impact,
        "gate4": {
            "status": "not_applicable_shadow_only",
            "reason": "No executable trading logic changed; canonical before/after metrics are unchanged.",
        },
        "primary_rows_for_audit": primary_rows,
    }

    artifact = ARTIFACT_DIR / "sec_leadership_change_reaction_shadow.json"
    _write_json(artifact, report)

    report_for_logs = dict(report)
    report_for_logs.pop("primary_rows_for_audit", None)
    _write_json(LOG_DIR / f"{EXPERIMENT_ID}.json", report_for_logs)
    _write_json(
        TICKET_DIR / f"{EXPERIMENT_ID}.json",
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "SEC leadership-change negative-reaction shadow alpha",
            "status": status,
            "summary": reason,
            "artifact": str(artifact.relative_to(ROOT)),
            "production_impact": production_impact,
        },
    )
    audit_path = _write_audit(report)
    report_for_logs["audit_path"] = str(audit_path.relative_to(ROOT))

    jsonl_record = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": generated_at,
        "hypothesis": report["hypothesis"],
        "change_type": "shadow_alpha_measurement",
        "classification": "alpha_search",
        "parameters": report["parameters"],
        "date_range": WINDOWS,
        "market_regime_summary": "canonical three-window evaluation",
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "expected_value_score_delta": report["expected_value_score_delta"],
        "decision": status,
        "rejection_reason": None if status.startswith("shadow_promising") else reason,
        "production_impact": production_impact,
        "artifact": str(artifact.relative_to(ROOT)),
        "notes": reason,
    }
    _append_jsonl(EXPERIMENT_LOG, jsonl_record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": status,
                "reason": reason,
                "primary_forward_10d": report["branches"][
                    "leadership_change_negative_reaction"
                ]["forward_10d"],
                "artifact": str(artifact.relative_to(ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
