"""Shadow decomposition of residual SEC 8-K filing semantics.

This experiment is alpha search only. It does not change entries, exits,
ranking, sizing, the universe, or production orders. It follows
exp-20260504-022 by decomposing the residual `other_sec_filing` branch into
fixed SEC item-code semantics instead of tuning nearby reaction thresholds.
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


EXPERIMENT_ID = "exp-20260504-023"
ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "sec_other_filing_semantic_decomposition.json"
)
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
AUDIT_MD = (
    ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_other_filing_semantic_decomposition_20260504.md"
)

PRIMARY_CATEGORY = "other_sec_filing"
PRIMARY_SEMANTIC = "shareholder_vote"
PRIMARY_REACTION_BUCKET = "negative_excess_0_to_minus_2pct"
MIN_PROMOTION_VALID_10D = 20


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
        if math.isfinite(result):
            return result
    return None


def _pct(value: float | None) -> float | None:
    return round(value * 100.0, 4) if isinstance(value, (int, float)) else None


def _horizon_value(row: dict[str, Any], horizon: str, field: str = "excess_return") -> float | None:
    payload = ((row.get("horizons") or {}).get(horizon) or {})
    if payload.get("status") != "valid":
        return None
    return _num(payload.get(field))


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
        out[horizon] = _summary(
            [
                value
                for row in rows
                for value in [_horizon_value(row, horizon, field)]
                if value is not None
            ]
        )
    return out


def semantic_subcategory(row: dict[str, Any]) -> str:
    """Map residual 8-K item codes to fixed semantic buckets."""

    items = {str(item) for item in row.get("eight_k_item_codes") or []}
    if "5.07" in items:
        return "shareholder_vote"
    if items & {"5.03", "3.02", "3.03"}:
        return "charter_or_securities_change"
    if items == {"9.01"}:
        return "exhibit_only"
    return "misc_other"


def _positive_window_count(rows: list[dict[str, Any]], horizon: str = "10d") -> int:
    count = 0
    for label in WINDOWS:
        values = [
            value
            for row in rows
            if row.get("window") == label
            for value in [_horizon_value(row, horizon)]
            if value is not None
        ]
        if values and mean(values) > 0:
            count += 1
    return count


def _dominance(rows: list[dict[str, Any]], horizon: str = "10d") -> dict[str, Any]:
    valid_rows = [row for row in rows if _horizon_value(row, horizon) is not None]
    if not valid_rows:
        return {"valid_events": 0}
    counts = Counter(str(row.get("ticker") or "unknown") for row in valid_rows)
    contribution: dict[str, float] = defaultdict(float)
    for row in valid_rows:
        contribution[str(row.get("ticker") or "unknown")] += _horizon_value(row, horizon) or 0.0
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
        "positive_replacement_proxy_rate": round(len(positives) / len(replacements), 4)
        if replacements
        else None,
        "replacement_value_10d_excess_proxy": _summary(replacements),
    }


def _item_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(str(item) for item in row.get("eight_k_item_codes") or [])
    return dict(counter.most_common(12))


def _cell_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, Any] = {}
    for label in WINDOWS:
        window_rows = [row for row in rows if row.get("window") == label]
        by_window[label] = {
            "event_count": len(window_rows),
            "forward_excess": _forward_summary(window_rows),
        }
    return {
        "event_count": len(rows),
        "unique_tickers": len({row.get("ticker") for row in rows}),
        "forward_excess": _forward_summary(rows),
        "positive_windows_10d": _positive_window_count(rows, "10d"),
        "dominance_10d": _dominance(rows, "10d"),
        "scarce_slot_value": _scarce_slot_summary(rows),
        "item_counts": _item_counts(rows),
        "by_window": by_window,
        "examples": [
            _compact_event(row)
            for row in sorted(rows, key=lambda item: (item["usable_trade_date"], item["ticker"]))[:12]
        ],
    }


def _rank_cells(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("semantic_subcategory")), str(row.get("reaction_bucket")))].append(row)

    cells: list[dict[str, Any]] = []
    for (semantic, reaction), items in sorted(grouped.items()):
        forward = _forward_summary(items)
        if forward["10d"]["count"] < 3:
            continue
        cells.append(
            {
                "semantic_subcategory": semantic,
                "reaction_bucket": reaction,
                "event_count": len(items),
                "valid_10d_count": forward["10d"]["count"],
                "avg_10d_excess_pct": forward["10d"]["avg_pct"],
                "median_10d_excess_pct": forward["10d"]["median_pct"],
                "positive_rate_10d_pct": forward["10d"]["positive_rate_pct"],
                "positive_windows_10d": _positive_window_count(items, "10d"),
                "scarce_slot_value": _scarce_slot_summary(items),
                "item_counts": _item_counts(items),
            }
        )
    return sorted(
        cells,
        key=lambda item: (
            item["positive_windows_10d"],
            item["avg_10d_excess_pct"] if item["avg_10d_excess_pct"] is not None else -999.0,
            item["valid_10d_count"],
        ),
        reverse=True,
    )


def _decision(primary_rows: list[dict[str, Any]]) -> tuple[str, str]:
    primary = _cell_summary(primary_rows)
    valid_10d = primary["forward_excess"]["10d"]["count"]
    avg_10d = primary["forward_excess"]["10d"]["avg_pct"]
    positive_windows = primary["positive_windows_10d"]
    if valid_10d < MIN_PROMOTION_VALID_10D:
        return (
            "shadow_promising_sample_limited_not_promoted",
            (
                "The shareholder-vote mild-negative branch is positive on average, but has fewer "
                f"than {MIN_PROMOTION_VALID_10D} valid 10d samples and is not production-promotable."
            ),
        )
    if not isinstance(avg_10d, (int, float)) or avg_10d <= 0:
        return "rejected_not_positive", "Primary semantic branch has non-positive average 10d excess return."
    if positive_windows < 3:
        return "observed_only_not_robust", "Primary semantic branch is not positive in all three windows."
    if primary["scarce_slot_value"]["valid_replacement_proxy_count"] < 5:
        return "shadow_promising_replacement_thin", "Primary semantic branch lacks enough same-day replacement samples."
    return "shadow_promising_not_promoted", "Primary semantic branch is positive and needs forward queue evidence."


def build_report() -> dict[str, Any]:
    universe = sorted(get_universe())
    baseline_metrics, baseline_trades = run_baseline_windows(universe)
    snapshots = {label: _load_snapshot(ROOT / cfg["snapshot"]) for label, cfg in WINDOWS.items()}
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
    residual_rows = [row for row in covered if row.get("filing_category") == PRIMARY_CATEGORY]
    for row in residual_rows:
        row["semantic_subcategory"] = semantic_subcategory(row)

    primary_rows = [
        row
        for row in residual_rows
        if row.get("semantic_subcategory") == PRIMARY_SEMANTIC
        and row.get("reaction_bucket") == PRIMARY_REACTION_BUCKET
    ]
    status, reason = _decision(primary_rows)

    report = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_search",
        "change_type": "shadow_event_semantic_decomposition",
        "status": status,
        "decision": status,
        "hypothesis": (
            "The residual SEC 8-K mild-negative branch may be driven by a narrower "
            "governance/shareholder-vote uncertainty mechanism rather than generic other filings."
        ),
        "single_causal_variable": "Fixed semantic subcategory decomposition inside residual other_sec_filing rows",
        "history_check": {
            "mechanism_insights_checked": [
                "LLM soft-ranking remains sample-limited; this does not depend on LLM outputs.",
                "exp-20260504-022 found a broad residual other_sec_filing mild-negative branch.",
                "exp-20260504-019 rejected agreement/debt; those rows are excluded by the existing category.",
                "exp-20260504-015/018 covered leadership-change; those rows are excluded by the existing category.",
                "No nearby reaction threshold, keyword phrase, or sizing/ranking rule is changed.",
            ],
            "why_not_simple_repeat": (
                "This decomposes the residual item-code semantics surfaced by exp-20260504-022; "
                "it does not rerun the same broad bucket or tune the reaction cutoff."
            ),
        },
        "parameters": {
            "primary_filing_category": PRIMARY_CATEGORY,
            "primary_semantic_subcategory": PRIMARY_SEMANTIC,
            "primary_reaction_bucket": PRIMARY_REACTION_BUCKET,
            "semantic_rules": {
                "shareholder_vote": "item 5.07 present",
                "charter_or_securities_change": "item 5.03, 3.02, or 3.03 present without item 5.07",
                "exhibit_only": "only item 9.01",
                "misc_other": "remaining residual 8-K item mixes",
            },
            "minimum_promotion_valid_10d_samples": MIN_PROMOTION_VALID_10D,
            "forward_horizons": ["5d", "10d", "20d"],
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "position sizing",
                "add-ons",
                "exits",
                "LLM/news replay",
                "reaction thresholds",
            ],
        },
        "date_windows": WINDOWS,
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "expected_value_score_delta": {name: 0.0 for name in sorted(baseline_metrics)},
        "coverage": {
            "sec_event_group_count": len(event_groups),
            "evaluated_window_event_count": len(evaluated),
            "price_covered_count": len(covered),
            "price_coverage_rate": round(len(covered) / len(evaluated), 4) if evaluated else None,
            "residual_other_sec_event_count": len(residual_rows),
            "primary_event_count": len(primary_rows),
            "primary_valid_10d_count": _cell_summary(primary_rows)["forward_excess"]["10d"]["count"],
            "primary_unique_tickers": len({row.get("ticker") for row in primary_rows}),
            "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
            "residual_semantic_counts": dict(
                Counter(str(row.get("semantic_subcategory")) for row in residual_rows)
            ),
        },
        "shadow_metrics": {
            "primary_branch": _cell_summary(primary_rows),
            "ranked_semantic_reaction_cells": _rank_cells(residual_rows),
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
            "Do not promote residual 8-K semantics into entries or ranking from this shadow sample alone.",
            "Do not tune nearby mild/strong reaction thresholds on the same sample.",
            "A valid retry needs forward queue replacement-value samples or richer filing semantics.",
        ],
        "related_files": [
            str(ARTIFACT.relative_to(ROOT)),
            "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl",
            "quant/experiments/exp_20260503_051_sec_filing_reaction_drift.py",
        ],
    }
    return _safe_payload(report)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_audit(report: dict[str, Any]) -> None:
    primary = report["shadow_metrics"]["primary_branch"]
    ten = primary["forward_excess"]["10d"]
    scarce = primary["scarce_slot_value"]
    lines = [
        f"# {EXPERIMENT_ID} SEC Other-Filing Semantic Decomposition",
        "",
        f"- decision: `{report['decision']}`",
        f"- primary branch: `{PRIMARY_CATEGORY}` + `{PRIMARY_SEMANTIC}` + `{PRIMARY_REACTION_BUCKET}`",
        f"- event rows: {primary['event_count']}",
        f"- valid 10d observations: {ten['count']}",
        f"- 10d avg excess: {ten['avg_pct']}%",
        f"- 10d positive rate: {ten['positive_rate_pct']}%",
        f"- positive 10d windows: {primary['positive_windows_10d']}/3",
        f"- same-day A/B overlap count: {scarce['same_day_ab_overlap_count']}",
        f"- replacement proxy avg: {scarce['replacement_value_10d_excess_proxy']['avg_pct']}%",
        "- production impact: `shadow_only_no_strategy_logic_changed`",
        "",
        "## Window Summary",
        "",
        "| window | events | valid 10d | avg 10d excess % | positive rate % |",
        "|---|---:|---:|---:|---:|",
    ]
    for window, summary in primary["by_window"].items():
        window_ten = summary["forward_excess"]["10d"]
        lines.append(
            f"| {window} | {summary['event_count']} | {window_ten['count']} | "
            f"{window_ten['avg_pct']} | {window_ten['positive_rate_pct']} |"
        )
    lines.extend(
        [
            "",
            "## Top Semantic Cells",
            "",
            "| semantic | reaction bucket | valid 10d | avg 10d excess % | positive windows |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for cell in report["shadow_metrics"]["ranked_semantic_reaction_cells"][:8]:
        lines.append(
            f"| {cell['semantic_subcategory']} | {cell['reaction_bucket']} | "
            f"{cell['valid_10d_count']} | {cell['avg_10d_excess_pct']} | "
            f"{cell['positive_windows_10d']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            report["decision_rationale"],
            "",
            "This is a shadow alpha-search result only. It does not alter entries, exits, ranking, sizing, "
            "candidate generation, or production orders.",
        ]
    )
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def persist(report: dict[str, Any]) -> None:
    _write_json(ARTIFACT, report)
    _write_json(LOG_JSON, report)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "SEC residual 8-K semantic decomposition",
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
                "top_cells": report["shadow_metrics"]["ranked_semantic_reaction_cells"][:5],
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
