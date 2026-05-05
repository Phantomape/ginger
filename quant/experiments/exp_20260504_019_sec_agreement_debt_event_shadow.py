"""Shadow check for SEC agreement/debt 8-K event packets.

This experiment does not change trading behavior. It measures whether PIT-safe
8-K agreement/debt disclosures (`agreement_or_debt`) look like a separate event
source with useful forward returns and limited same-day A/B overlap.
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


EXPERIMENT_ID = "exp-20260504-019"
ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260504_019_sec_agreement_debt_event_shadow.json"
)

PRIMARY_CATEGORY = "agreement_or_debt"


def _excess(row: dict[str, Any], horizon: str) -> float | None:
    value = ((row.get("horizons") or {}).get(horizon) or {}).get("excess_return")
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def _raw_return(row: dict[str, Any], horizon: str) -> float | None:
    value = ((row.get("horizons") or {}).get(horizon) or {}).get("return")
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def _pct(value: float | None) -> float | None:
    return round(value * 100.0, 4) if isinstance(value, (int, float)) else None


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


def _forward_summary(rows: list[dict[str, Any]], field: str = "excess") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon in ("5d", "10d", "20d"):
        values = []
        for row in rows:
            value = _raw_return(row, horizon) if field == "raw" else _excess(row, horizon)
            if value is not None:
                values.append(value)
        out[horizon] = _summary(values)
    return out


def _group_summary(rows: list[dict[str, Any]], group_key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(group_key) or "unknown")].append(row)
    return {
        key: {
            "event_count": len(items),
            "unique_tickers": len({item["ticker"] for item in items}),
            "forward_excess": _forward_summary(items, "excess"),
        }
        for key, items in sorted(grouped.items())
    }


def _dominance(rows: list[dict[str, Any]], horizon: str = "10d") -> dict[str, Any]:
    valid_rows = [row for row in rows if _excess(row, horizon) is not None]
    if not valid_rows:
        return {"valid_events": 0}
    counts = Counter(row["ticker"] for row in valid_rows)
    contribution: dict[str, float] = defaultdict(float)
    for row in valid_rows:
        contribution[row["ticker"]] += _excess(row, horizon) or 0.0
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


def _positive_window_count(rows: list[dict[str, Any]], horizon: str = "10d") -> int:
    count = 0
    for window_rows in _rows_by_window(rows).values():
        values = [_excess(row, horizon) for row in window_rows]
        values = [value for value in values if value is not None]
        if values and mean(values) > 0:
            count += 1
    return count


def _rows_by_window(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["window"]].append(row)
    return dict(grouped)


def _decision(rows: list[dict[str, Any]]) -> tuple[str, str]:
    values = [_excess(row, "10d") for row in rows]
    values = [value for value in values if value is not None]
    if len(values) < 20:
        return "observed_only_insufficient_sample", "The event packet has fewer than 20 valid 10d samples."
    if mean(values) <= 0:
        return "observed_only_not_promoted", "The event packet has non-positive average 10d excess return."
    if _positive_window_count(rows, "10d") < 2:
        return "observed_only_not_promoted", "The event packet is not positive in at least two canonical windows."
    dominance = _dominance(rows, "10d")
    if (dominance.get("top_abs_contribution_share_pct") or 100.0) > 50.0:
        return "observed_only_concentrated", "The event packet is positive but dominated by one ticker contribution."
    return (
        "shadow_promising_not_promoted",
        "The event packet is positive across multiple windows but remains shadow-only pending replacement-value evidence.",
    )


def _metrics_delta_zero(metrics: dict[str, Any]) -> dict[str, float]:
    return {name: 0.0 for name in sorted(metrics)}


def build_report() -> dict[str, Any]:
    universe = sorted(get_universe())
    baseline_metrics, baseline_trades = run_baseline_windows(universe)
    event_groups = load_event_groups(SEC_EVENTS_PATH)
    snapshots = {
        label: _load_snapshot(ROOT / cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }

    evaluated: list[dict[str, Any]] = []
    for label, cfg in WINDOWS.items():
        snapshot = snapshots[label]
        spy_rows = snapshot.get("SPY") or []
        for group in event_groups:
            usable_date = group["usable_trade_date"]
            if cfg["start"] <= usable_date <= cfg["end"]:
                evaluated.append(evaluate_group(group, snapshot, spy_rows, label))

    covered = [row for row in evaluated if row.get("price_status") == "covered"]
    covered, slot_summary = attach_slot_conflicts(covered, baseline_trades, snapshots)
    primary_rows = [row for row in covered if row.get("filing_category") == PRIMARY_CATEGORY]
    status, reason = _decision(primary_rows)

    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lane": "alpha_discovery",
        "status": status,
        "decision": status,
        "hypothesis": (
            "PIT-safe SEC 8-K material agreement/debt event packets may surface a "
            "non-overlapping external event alpha source distinct from earnings text, "
            "leadership changes, Form 4, and raw reaction gates."
        ),
        "change_type": "new_strategy_shadow",
        "single_causal_variable": "SEC agreement-or-debt 8-K event packet",
        "history_check": {
            "guardrails_checked": [
                "not post-news continuation",
                "not Form 4 threshold or role filter",
                "not SEC positive-reaction gate",
                "not Companyfacts simple scoring",
                "not SEC negative-language direct promotion",
                "not SEC negative-reaction replacement replay",
                "not leadership-change reaction threshold tuning",
            ],
            "why_not_repeat": (
                "This freezes filing category as the only causal variable and does not tune "
                "reaction thresholds, text phrases, owner roles, or existing sizing/cap logic."
            ),
        },
        "parameters": {
            "primary_filing_category": PRIMARY_CATEGORY,
            "event_unit": "ticker + usable_trade_date, same-day filings grouped",
            "entry_timing": "next trading-day open after public filing/reaction day",
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
            ],
        },
        "date_windows": WINDOWS,
        "market_regime_summary": {label: cfg["state_note"] for label, cfg in WINDOWS.items()},
        "before_metrics": baseline_metrics,
        "after_metrics": baseline_metrics,
        "expected_value_score_delta": _metrics_delta_zero(baseline_metrics),
        "coverage": {
            "sec_event_group_count": len(event_groups),
            "evaluated_window_event_count": len(evaluated),
            "price_covered_count": len(covered),
            "price_coverage_rate": round(len(covered) / len(evaluated), 4) if evaluated else None,
            "primary_event_count": len(primary_rows),
            "primary_valid_10d_count": _forward_summary(primary_rows)["10d"]["count"],
            "primary_unique_tickers": len({row["ticker"] for row in primary_rows}),
            "by_price_status": dict(Counter(row.get("price_status") for row in evaluated)),
        },
        "shadow_metrics": {
            "agreement_or_debt_packet": {
                "event_count": len(primary_rows),
                "unique_tickers": len({row["ticker"] for row in primary_rows}),
                "forward_raw": _forward_summary(primary_rows, "raw"),
                "forward_excess": _forward_summary(primary_rows, "excess"),
                "by_window": _group_summary(primary_rows, "window"),
                "by_reaction_bucket": _group_summary(primary_rows, "reaction_bucket"),
                "dominance_10d": _dominance(primary_rows, "10d"),
                "examples": [_compact_event(row) for row in primary_rows[:20]],
            },
            "all_sec_events_by_category": _group_summary(covered, "filing_category"),
            "slot_conflict": slot_summary,
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
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "next_retry_requires": [
            "Do not promote this packet without slot-aware replacement value versus same-day A/B alternatives.",
            "Do not tune nearby reaction buckets or 8-K item combinations from this result alone.",
            "A valid retry needs richer agreement semantics, contract value context, or forward queue evidence.",
        ],
        "related_files": [
            str(ARTIFACT.relative_to(ROOT)),
            "data/non_ohlcv/sec_filing_events_20241002_20260421.jsonl",
        ],
    }


def main() -> int:
    report = build_report()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(_safe_payload(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    primary = report["shadow_metrics"]["agreement_or_debt_packet"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": report["status"],
                "reason": report["decision_rationale"],
                "coverage": report["coverage"],
                "primary_10d_excess": primary["forward_excess"]["10d"],
                "primary_by_window": primary["by_window"],
                "artifact": str(ARTIFACT.relative_to(ROOT)),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
