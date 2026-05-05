"""Universe scout for SEC leadership-change negative-reaction candidates.

This is a shadow-only audit. It does not add tickers to the production
universe and does not alter entries, ranking, sizing, exits, or orders.
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

from filter import WATCHLIST  # noqa: E402


EXPERIMENT_ID = "exp-20260504-018"
SOURCE_EXPERIMENT_ID = "exp-20260504-015"
SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / SOURCE_EXPERIMENT_ID
    / "sec_leadership_change_reaction_shadow.json"
)
OUT_PATH = (
    ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260504_018_sec_leadership_negative_reaction_universe.json"
)

PRIMARY_BRANCH = "leadership_change_negative_reaction"
HORIZONS = ("5d", "10d", "20d")


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_sanitize(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "p25": None,
            "p75": None,
            "win_rate": None,
            "best": None,
            "worst": None,
        }
    ordered = sorted(values)
    p25_idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.25)))
    p75_idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.75)))
    return {
        "count": len(values),
        "avg": round(mean(values), 6),
        "median": round(median(values), 6),
        "p25": round(ordered[p25_idx], 6),
        "p75": round(ordered[p75_idx], 6),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
        "best": round(max(values), 6),
        "worst": round(min(values), 6),
    }


def _pct_summary(values: list[float]) -> dict[str, Any]:
    summary = _summary(values)
    out: dict[str, Any] = {}
    for key, value in summary.items():
        if key == "count" or value is None:
            out[key] = value
        elif key == "win_rate":
            out[key] = round(value * 100.0, 2)
        elif isinstance(value, (int, float)):
            out[key] = round(value * 100.0, 4)
        else:
            out[key] = value
    return out


def _horizon_value(row: dict[str, Any], horizon: str, key: str) -> float | None:
    value = ((row.get("horizons") or {}).get(horizon) or {}).get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _valid_rows(rows: list[dict[str, Any]], horizon: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if ((row.get("horizons") or {}).get(horizon) or {}).get("status") == "valid"
    ]


def _forward_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for horizon in HORIZONS:
        out[horizon] = {
            "return_pct": _pct_summary(
                [
                    value
                    for row in rows
                    for value in [_horizon_value(row, horizon, "return")]
                    if value is not None
                ]
            ),
            "excess_return_pct": _pct_summary(
                [
                    value
                    for row in rows
                    for value in [_horizon_value(row, horizon, "excess_return")]
                    if value is not None
                ]
            ),
        }
    return out


def _group_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) if row.get(key) is not None else "unknown")].append(row)
    return {
        group_key: {
            "candidate_count": len(group_rows),
            "unique_tickers": len({row.get("ticker") for row in group_rows}),
            "forward_distribution": _forward_distribution(group_rows),
        }
        for group_key, group_rows in sorted(grouped.items())
    }


def _liquidity_bucket(avg_dollar_volume: float | None) -> str:
    if avg_dollar_volume is None:
        return "adv_unknown"
    if avg_dollar_volume >= 20_000_000:
        return "adv_ge_20m"
    if avg_dollar_volume >= 5_000_000:
        return "adv_5m_20m"
    return "adv_lt_5m"


def _compact_candidate(row: dict[str, Any], current_universe: set[str]) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    return {
        "ticker": ticker,
        "window": row.get("window"),
        "entry_date": row.get("entry_date"),
        "usable_trade_date": row.get("usable_trade_date"),
        "reaction_date": row.get("reaction_date"),
        "reaction_excess_return_pct": (
            round(float(row["reaction_excess_return"]) * 100.0, 4)
            if isinstance(row.get("reaction_excess_return"), (int, float))
            else None
        ),
        "avg_dollar_volume_20d": row.get("avg_dollar_volume_20d"),
        "liquidity_bucket": row.get("liquidity_bucket"),
        "in_current_universe": ticker in current_universe,
        "same_day_core_trade_count": row.get("same_day_core_trade_count"),
        "slot_conflict_proxy": bool(row.get("slot_conflict_proxy")),
        "replacement_value_10d_excess_proxy_pct": (
            round(float(row["replacement_value_10d_excess_proxy"]) * 100.0, 4)
            if isinstance(row.get("replacement_value_10d_excess_proxy"), (int, float))
            else None
        ),
        "horizons": row.get("horizons"),
    }


def _current_universe() -> set[str]:
    """Read the current watchlist plus open positions without importing yfinance."""
    universe = {str(ticker).upper() for ticker in WATCHLIST}
    positions_path = ROOT / "data" / "open_positions.json"
    if positions_path.exists():
        try:
            payload = _load_json(positions_path)
        except Exception:
            payload = {}
        for position in payload.get("positions") or []:
            ticker = position.get("ticker")
            if ticker:
                universe.add(str(ticker).upper())
    return universe


def _scarce_slot_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    conflict_rows = [row for row in rows if row.get("slot_conflict_proxy")]
    replacement_values = [
        float(row["replacement_value_10d_excess_proxy"])
        for row in rows
        if isinstance(row.get("replacement_value_10d_excess_proxy"), (int, float))
    ]
    return {
        "same_day_ab_overlap_count": len(conflict_rows),
        "same_day_ab_overlap_rate": round(len(conflict_rows) / len(rows), 4) if rows else None,
        "valid_replacement_proxy_count": len(replacement_values),
        "positive_replacement_proxy_count": sum(1 for value in replacement_values if value > 0),
        "positive_replacement_proxy_rate": (
            round(sum(1 for value in replacement_values if value > 0) / len(replacement_values), 4)
            if replacement_values
            else None
        ),
        "replacement_value_10d_excess_proxy_pct": _pct_summary(replacement_values),
    }


def build_payload() -> dict[str, Any]:
    source = _load_json(SOURCE_ARTIFACT)
    current_universe = _current_universe()
    primary_rows = list(source.get("primary_rows_for_audit") or [])
    for row in primary_rows:
        row["ticker"] = str(row.get("ticker") or "").upper()
        row["liquidity_bucket"] = _liquidity_bucket(row.get("avg_dollar_volume_20d"))
        row["in_current_universe"] = row["ticker"] in current_universe

    valid_10d_rows = _valid_rows(primary_rows, "10d")
    valid_20d_rows = _valid_rows(primary_rows, "20d")
    in_current = [row for row in primary_rows if row["in_current_universe"]]
    outside_current = [row for row in primary_rows if not row["in_current_universe"]]
    avg_dollar_volumes = [
        float(row["avg_dollar_volume_20d"])
        for row in primary_rows
        if isinstance(row.get("avg_dollar_volume_20d"), (int, float))
    ]
    liq_counts = Counter(row.get("liquidity_bucket") for row in primary_rows)
    source_branch = (source.get("branches") or {}).get(PRIMARY_BRANCH) or {}
    all_leadership = (source.get("branches") or {}).get("leadership_change_all") or {}

    decision = "observed_only_not_promoted"
    decision_reason = (
        "The source is liquid and forward-positive, but scarce-slot evidence is too thin "
        "for production promotion."
    )
    scarce_slot = _scarce_slot_summary(primary_rows)
    if (
        scarce_slot["valid_replacement_proxy_count"] >= 5
        and (scarce_slot["replacement_value_10d_excess_proxy_pct"].get("avg") or 0) <= 0
    ):
        decision = "rejected_scarce_slot_value"
        decision_reason = "The source fails scarce-slot replacement value against same-day A/B alternatives."

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "universe_scout",
        "change_type": "universe_expansion",
        "source_experiment_id": SOURCE_EXPERIMENT_ID,
        "hypothesis": (
            "A frozen SEC 8-K leadership-change negative-reaction shadow universe can provide "
            "liquid, covered, low-overlap candidates with positive forward returns and measurable "
            "scarce-slot value without adding tickers to production."
        ),
        "single_causal_variable": "SEC leadership-change negative-reaction shadow universe definition",
        "history_check": {
            "not_repeating_sec_positive_reaction": (
                "Uses the fixed leadership-change semantic category and fixed <= -2% excess reaction "
                "branch from exp-20260504-015, not the rejected broad positive SEC reaction gate."
            ),
            "not_repeating_sec_negative_language_queue": (
                "This is Item 5.02-style leadership-change context, not Item 2.02 negative-language "
                "keyword tuning or direct queue promotion."
            ),
            "not_a_threshold_sweep": "No parameters were tuned; the source definition is frozen.",
        },
        "parameters": {
            "filing_form": "8-K",
            "semantic_category": "leadership_change",
            "item_code_family": "5.02-style leadership change",
            "reaction_filter": "first public excess reaction <= -2%",
            "entry_timing": "next available trading day after usable public reaction date",
            "forward_horizons": list(HORIZONS),
            "production_enabled": False,
        },
        "baseline_metrics": source.get("baseline_metrics"),
        "before_metrics": source.get("before_metrics"),
        "after_metrics": source.get("after_metrics"),
        "expected_value_score_delta": source.get("expected_value_score_delta"),
        "data_coverage": {
            "source_artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)),
            "all_leadership_event_count": all_leadership.get("event_count"),
            "candidate_source_event_count": len(primary_rows),
            "candidate_source_unique_tickers": len({row["ticker"] for row in primary_rows}),
            "valid_5d_count": len(_valid_rows(primary_rows, "5d")),
            "valid_10d_count": len(valid_10d_rows),
            "valid_20d_count": len(valid_20d_rows),
            "valid_10d_coverage_rate": round(len(valid_10d_rows) / len(primary_rows), 4) if primary_rows else None,
            "valid_20d_coverage_rate": round(len(valid_20d_rows) / len(primary_rows), 4) if primary_rows else None,
            "current_universe_overlap_count": len(in_current),
            "current_universe_overlap_rate": round(len(in_current) / len(primary_rows), 4) if primary_rows else None,
            "outside_current_universe_count": len(outside_current),
            "same_day_ab_overlap_count": scarce_slot["same_day_ab_overlap_count"],
            "same_day_ab_overlap_rate": scarce_slot["same_day_ab_overlap_rate"],
        },
        "liquidity": {
            "avg_dollar_volume_20d_usd": _summary(avg_dollar_volumes),
            "liquidity_bucket_counts": dict(sorted(liq_counts.items())),
            "adv_ge_5m_count": sum(
                1 for row in primary_rows if row.get("liquidity_bucket") in {"adv_5m_20m", "adv_ge_20m"}
            ),
            "adv_ge_20m_count": sum(1 for row in primary_rows if row.get("liquidity_bucket") == "adv_ge_20m"),
        },
        "candidate_counts": {
            "by_window": dict(Counter(row.get("window") for row in primary_rows)),
            "by_ticker_top": dict(Counter(row["ticker"] for row in primary_rows).most_common(12)),
            "source_branch_event_count": source_branch.get("event_count"),
        },
        "forward_returns": {
            "overall": _forward_distribution(primary_rows),
            "by_window": _group_summary(primary_rows, "window"),
            "in_current_universe": _forward_distribution(in_current),
            "outside_current_universe": _forward_distribution(outside_current),
        },
        "scarce_slot_value": scarce_slot,
        "dominance": source_branch.get("dominance_10d"),
        "ticker_rank_10d": source.get("ticker_rank_10d_primary"),
        "survivorship_and_data_bias": {
            "survivorship_bias_present": True,
            "point_in_time_universe_qualified": False,
            "production_trade_enabled": False,
            "bias_notes": [
                "The historical event set is sourced from currently available SEC-derived artifacts and current ticker mapping.",
                "The current universe overlap uses today's get_universe output, not a point-in-time universe ledger.",
                "Same-day A/B overlap is a proxy from replayed accepted trades, not a full capacity-aware portfolio simulation.",
                "This artifact can justify forward observation or richer grading, not production ticker admission.",
            ],
        },
        "sample_candidates": [_compact_candidate(row, current_universe) for row in primary_rows],
        "decision": {
            "status": decision,
            "reason": decision_reason,
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
            "production_universe_changed": False,
            "notes": "Shadow universe audit only; no production universe or strategy behavior changed.",
        },
        "next_action": (
            "Do not promote. If pursued, add a default-off forward observation queue or LLM semantic "
            "grader only after freezing same-day alternatives for replacement-value attribution."
        ),
    }
    return payload


def main() -> int:
    payload = build_payload()
    _write_json(OUT_PATH, payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "artifact": str(OUT_PATH.relative_to(ROOT)),
                "candidate_count": payload["data_coverage"]["candidate_source_event_count"],
                "valid_10d_count": payload["data_coverage"]["valid_10d_count"],
                "same_day_ab_overlap_rate": payload["data_coverage"]["same_day_ab_overlap_rate"],
                "forward_10d_excess_pct": payload["forward_returns"]["overall"]["10d"]["excess_return_pct"],
                "scarce_slot_value_pct": payload["scarce_slot_value"]["replacement_value_10d_excess_proxy_pct"],
                "production_universe_changed": False,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
