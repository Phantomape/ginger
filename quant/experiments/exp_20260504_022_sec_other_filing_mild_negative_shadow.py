"""Shadow check for other SEC filings with mild negative reactions.

This experiment does not change trading behavior. It tests whether the existing
SEC filing taxonomy has a separate `other_sec_filing` branch where a mild first
public excess selloff is followed by positive 10-trading-day drift.
"""

from __future__ import annotations

import json
import math
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

from data_layer import get_universe  # noqa: E402
from experiments.exp_20260503_051_sec_filing_reaction_drift import (  # noqa: E402
    SEC_EVENTS_PATH,
    WINDOWS,
    _compact_event,
    _load_snapshot,
    _safe_payload,
    attach_slot_conflicts,
    evaluate_group,
    load_event_groups,
    run_baseline_windows,
)


EXPERIMENT_ID = "exp-20260504-022"
ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "sec_other_filing_mild_negative_shadow.json"
)
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
AUDIT_MD = (
    ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_other_filing_mild_negative_shadow_exp022_20260504.md"
)

PRIMARY_CATEGORY = "other_sec_filing"
PRIMARY_REACTION_BUCKET = "negative_excess_0_to_minus_2pct"


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
        if math.isfinite(result):
            return result
    return None


def _pct(value: float | None) -> float | None:
    return round(value * 100.0, 4) if isinstance(value, (int, float)) else None


def _horizon_value(row: dict[str, Any], horizon: str, field: str) -> float | None:
    return _num(((row.get("horizons") or {}).get(horizon) or {}).get(field))


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg_pct": None,
            "median_pct": None,
            "positive_rate_pct": None,
            "best_pct": None,
            "worst_pct": None,
        }
    positives = [value for value in values if value > 0]
    return {
        "count": len(values),
        "avg_pct": _pct(mean(values)),
        "median_pct": _pct(median(values)),
        "positive_rate_pct": round(len(positives) / len(values) * 100.0, 2),
        "best_pct": _pct(max(values)),
        "worst_pct": _pct(min(values)),
    }


def _forward_summary(rows: list[dict[str, Any]], field: str = "excess_return") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon in ("5d", "10d", "20d"):
        values = [
            value
            for row in rows
            for value in [_horizon_value(row, horizon, field)]
            if value is not None
        ]
        out[horizon] = _summary(values)
    return out


def _group_summary(rows: list[dict[str, Any]], group_key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = row.get(group_key)
        grouped[str(key if key is not None else "unknown")].append(row)
    return {
        key: {
            "event_count": len(items),
            "unique_tickers": len({item.get("ticker") for item in items}),
            "forward_excess": _forward_summary(items, "excess_return"),
        }
        for key, items in sorted(grouped.items())
    }


def _rows_by_window(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("window") or "unknown")].append(row)
    return dict(grouped)


def _positive_window_count(rows: list[dict[str, Any]], horizon: str = "10d") -> int:
    count = 0
    for label in WINDOWS:
        values = [
            value
            for row in rows
            if row.get("window") == label
            for value in [_horizon_value(row, horizon, "excess_return")]
            if value is not None
        ]
        if values and mean(values) > 0:
            count += 1
    return count


def _dominance(rows: list[dict[str, Any]], horizon: str = "10d") -> dict[str, Any]:
    valid_rows = [row for row in rows if _horizon_value(row, horizon, "excess_return") is not None]
    if not valid_rows:
        return {"valid_events": 0}
    counts = Counter(str(row.get("ticker") or "unknown") for row in valid_rows)
    contribution: dict[str, float] = defaultdict(float)
    for row in valid_rows:
        contribution[str(row.get("ticker") or "unknown")] += (
            _horizon_value(row, horizon, "excess_return") or 0.0
        )
    top_count_ticker, top_count = counts.most_common(1)[0]
    total_abs = sum(abs(value) for value in contribution.values())
    top_abs_share = max(abs(value) for value in contribution.values()) / total_abs if total_abs else None
    return {
        "valid_events": len(valid_rows),
        "unique_tickers": len(counts),
        "top_count_ticker": top_count_ticker,
        "top_count_share_pct": round(top_count / len(valid_rows) * 100.0, 2),
        "top_abs_contribution_share_pct": _pct(top_abs_share),
    }


def _item_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    forms: Counter[str] = Counter()
    bases: Counter[str] = Counter()
    items: Counter[str] = Counter()
    for row in rows:
        forms.update(str(value) for value in row.get("form_types") or [])
        bases.update(str(value) for value in row.get("form_bases") or [])
        items.update(str(value) for value in row.get("eight_k_item_codes") or [])
    return {
        "form_types": dict(forms.most_common(12)),
        "form_bases": dict(bases.most_common(12)),
        "eight_k_item_codes": dict(items.most_common(12)),
    }


def _scarce_slot_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conflicts = [row for row in rows if row.get("slot_conflict_proxy")]
    replacements = [
        value
        for row in rows
        for value in [_num(row.get("replacement_value_10d_excess_proxy"))]
        if value is not None
    ]
    positives = [value for value in replacements if value > 0]
    return {
        "same_day_ab_overlap_count": len(conflicts),
        "same_day_ab_overlap_rate": round(len(conflicts) / len(rows), 4) if rows else None,
        "valid_replacement_proxy_count": len(replacements),
        "positive_replacement_proxy_count": len(positives),
        "positive_replacement_proxy_rate": (
            round(len(positives) / len(replacements), 4) if replacements else None
        ),
        "replacement_value_10d_excess_proxy": _summary(replacements),
    }


def _decision(primary_rows: list[dict[str, Any]]) -> tuple[str, str]:
    values = [
        value
        for row in primary_rows
        for value in [_horizon_value(row, "10d", "excess_return")]
        if value is not None
    ]
    if len(values) < 20:
        return "observed_only_insufficient_sample", "Primary branch has fewer than 20 valid 10d samples."
    if mean(values) <= 0:
        return "observed_only_not_promoted", "Primary branch has non-positive average 10d excess return."
    if _positive_window_count(primary_rows, "10d") < 3:
        return "observed_only_not_promoted", "Primary branch is not positive in all three canonical windows."
    dominance = _dominance(primary_rows, "10d")
    if (dominance.get("top_abs_contribution_share_pct") or 100.0) > 50.0:
        return "shadow_promising_concentrated", "Primary branch is positive but dominated by one ticker."
    return (
        "shadow_promising_not_promoted",
        "Primary branch is positive in all three canonical windows, but remains shadow-only pending semantic and replacement-value evidence.",
    )


def _zero_delta(metrics: dict[str, Any]) -> dict[str, float]:
    return {name: 0.0 for name in sorted(metrics)}


def _compact_rows(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    return [_compact_event(row) for row in sorted(rows, key=lambda item: (item["usable_trade_date"], item["ticker"]))[:limit]]


def build_report() -> dict[str, Any]:
    universe = sorted(get_universe())
    baseline_metrics, baseline_trades = run_baseline_windows(universe)
    snapshots = {
        label: _load_snapshot(ROOT / cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }
    event_groups = load_event_groups(SEC_EVENTS_PATH)

    evaluated: list[dict[str, Any]] = []
    for label, cfg in WINDOWS.items():
        snapshot = snapshots[label]
        spy_rows = snapshot.get("SPY") or []
        for group in event_groups:
            usable_date = group["usable_trade_date"]
            if cfg["start"] <= usable_date <= cfg["end"]:
                evaluated.append(evaluate_group(group, snapshot, spy_rows, label))

    covered = [row for row in evaluated if row.get("price_status") == "covered"]
    covered, global_slot_summary = attach_slot_conflicts(covered, baseline_trades, snapshots)
    primary_rows = [
        row
        for row in covered
        if row.get("filing_category") == PRIMARY_CATEGORY
        and row.get("reaction_bucket") == PRIMARY_REACTION_BUCKET
    ]
    status, reason = _decision(primary_rows)

    report = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "change_type": "shadow_event_taxonomy",
        "status": status,
        "decision": status,
        "hypothesis": (
            "SEC filings that fall outside the already-tested earnings, agreement/debt, leadership, "
            "and FD/other 8-K buckets may create a mild uncertainty selloff that mean-reverts over "
            "the next 10 trading days."
        ),
        "single_causal_variable": "SEC other_sec_filing plus fixed mild negative reaction bucket",
        "history_check": {
            "mechanism_insights_checked": [
                "LLM soft-ranking remains sample-limited, so this run does not depend on it.",
                "exp-20260504-019 rejected agreement_or_debt; this excludes that category.",
                "exp-20260504-015/018 measured leadership-change; this excludes that category.",
                "exp-20260504-008/010/012 measured Item 2.02 negative-language packets; this excludes that category.",
                "The run does not tune nearby reaction thresholds; it uses a pre-existing reaction bucket.",
            ],
            "why_not_simple_repeat": (
                "This tests a previously unpromoted residual SEC filing category, not another "
                "leadership-change threshold or agreement/debt retry."
            ),
        },
        "parameters": {
            "primary_filing_category": PRIMARY_CATEGORY,
            "primary_reaction_bucket": PRIMARY_REACTION_BUCKET,
            "entry_timing": "next trading-day open after public filing/reaction day",
            "forward_horizons": ["5d", "10d", "20d"],
            "minimum_valid_10d_samples": 20,
            "required_positive_windows": 3,
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "add-ons",
                "exits",
                "LLM/news replay",
            ],
        },
        "date_windows": WINDOWS,
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "expected_value_score_delta": _zero_delta(baseline_metrics),
        "coverage": {
            "sec_event_group_count": len(event_groups),
            "evaluated_window_event_count": len(evaluated),
            "price_covered_count": len(covered),
            "price_coverage_rate": round(len(covered) / len(evaluated), 4) if evaluated else None,
            "primary_event_count": len(primary_rows),
            "primary_valid_10d_count": _forward_summary(primary_rows)["10d"]["count"],
            "primary_unique_tickers": len({row.get("ticker") for row in primary_rows}),
            "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
        },
        "shadow_metrics": {
            "primary_branch": {
                "event_count": len(primary_rows),
                "unique_tickers": len({row.get("ticker") for row in primary_rows}),
                "forward_raw": _forward_summary(primary_rows, "return"),
                "forward_excess": _forward_summary(primary_rows, "excess_return"),
                "by_window": _group_summary(primary_rows, "window"),
                "dominance_10d": _dominance(primary_rows, "10d"),
                "item_counts": _item_counts(primary_rows),
                "scarce_slot_value": _scarce_slot_summary(primary_rows),
                "examples": _compact_rows(primary_rows),
            },
            "all_other_sec_filing_by_reaction_bucket": _group_summary(
                [row for row in covered if row.get("filing_category") == PRIMARY_CATEGORY],
                "reaction_bucket",
            ),
            "all_sec_category_reaction_cells": _category_reaction_cells(covered),
            "global_slot_conflict": global_slot_summary,
        },
        "decision_rationale": reason,
        "gate4": {
            "applicable": False,
            "result": "not_applicable_shadow_only",
            "reason": "No executable strategy logic changed; canonical before/after metrics are unchanged by design.",
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_signal_generation": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "next_retry_requires": [
            "Do not promote this residual filing branch into entries or ranking from shadow evidence alone.",
            "Do not tune nearby mild/strong reaction thresholds on the same sample.",
            "A valid next step needs semantic decomposition of the residual filing forms or forward queue evidence with frozen same-day alternatives.",
        ],
        "related_files": [
            str(ARTIFACT.relative_to(ROOT)),
            "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl",
            "quant/experiments/exp_20260503_051_sec_filing_reaction_drift.py",
        ],
    }
    return _safe_payload(report)


def _category_reaction_cells(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row.get('filing_category')}|{row.get('reaction_bucket')}"].append(row)

    cells = []
    for key, items in sorted(grouped.items()):
        forward = _forward_summary(items, "excess_return")
        valid_10d = forward["10d"]["count"]
        if valid_10d < 8:
            continue
        cells.append({
            "cell": key,
            "event_count": len(items),
            "valid_10d_count": valid_10d,
            "positive_windows_10d": _positive_window_count(items, "10d"),
            "avg_10d_excess_pct": forward["10d"]["avg_pct"],
            "median_10d_excess_pct": forward["10d"]["median_pct"],
            "positive_rate_10d_pct": forward["10d"]["positive_rate_pct"],
            "scarce_slot_value": _scarce_slot_summary(items),
        })
    return {
        "min_valid_10d": 8,
        "ranked_by_avg_10d": sorted(
            cells,
            key=lambda item: (
                item["positive_windows_10d"],
                item["avg_10d_excess_pct"] if item["avg_10d_excess_pct"] is not None else -999.0,
                item["valid_10d_count"],
            ),
            reverse=True,
        ),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_audit(report: dict[str, Any]) -> None:
    primary = report["shadow_metrics"]["primary_branch"]
    scarce = primary["scarce_slot_value"]
    positive_windows = sum(
        1
        for summary in primary["by_window"].values()
        if isinstance(summary["forward_excess"]["10d"].get("avg_pct"), (int, float))
        and summary["forward_excess"]["10d"]["avg_pct"] > 0
    )
    lines = [
        f"# {EXPERIMENT_ID} SEC Other-Filing Mild Negative Shadow",
        "",
        f"- decision: `{report['decision']}`",
        f"- primary branch: `{PRIMARY_CATEGORY}` + `{PRIMARY_REACTION_BUCKET}`",
        f"- event rows: {primary['event_count']}",
        f"- valid 10d observations: {primary['forward_excess']['10d']['count']}",
        f"- 10d avg excess: {primary['forward_excess']['10d']['avg_pct']}%",
        f"- 10d positive rate: {primary['forward_excess']['10d']['positive_rate_pct']}%",
        f"- positive 10d windows: {positive_windows}/3",
        f"- same-day A/B overlap count: {scarce['same_day_ab_overlap_count']}",
        f"- replacement proxy avg: {scarce['replacement_value_10d_excess_proxy']['avg_pct']}%",
        f"- production impact: `shadow_only_no_strategy_logic_changed`",
        "",
        "## Window Summary",
        "",
        "| window | events | valid 10d | avg 10d excess % | positive rate % |",
        "|---|---:|---:|---:|---:|",
    ]
    for window, summary in primary["by_window"].items():
        ten = summary["forward_excess"]["10d"]
        lines.append(
            f"| {window} | {summary['event_count']} | {ten['count']} | "
            f"{ten['avg_pct']} | {ten['positive_rate_pct']} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        report["decision_rationale"],
        "",
        "This is a shadow alpha-search result only. It does not alter entries, exits, ranking, sizing, "
        "candidate generation, or production orders.",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist(report: dict[str, Any]) -> None:
    _write_json(ARTIFACT, report)
    _write_json(LOG_JSON, report)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "SEC other-filing mild selloff shadow",
            "status": report["status"],
            "summary": report["decision_rationale"],
            "artifact": str(ARTIFACT.relative_to(ROOT)),
            "production_impact": report["production_impact"],
        },
    )
    _write_audit(report)


def main() -> int:
    report = build_report()
    persist(report)
    primary = report["shadow_metrics"]["primary_branch"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": report["status"],
                "reason": report["decision_rationale"],
                "coverage": report["coverage"],
                "primary_10d_excess": primary["forward_excess"]["10d"],
                "primary_by_window": primary["by_window"],
                "scarce_slot_value": primary["scarce_slot_value"],
                "artifact": str(ARTIFACT.relative_to(ROOT)),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
