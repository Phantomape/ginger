"""Observed-only scout for Space official-or-primary event source quality.

This runner evaluates one source variable from the existing Space event-state
shadow ledger. It does not add tickers, slots, orders, sizing, ranking, exits,
or production signal logic.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260512-103"
SOURCE_TYPE = "official_or_primary_release"

LEDGER_PATH = REPO_ROOT / "data" / "space_catalyst_event_state_shadow_ledger.jsonl"
SUMMARY_PATH = REPO_ROOT / "data" / "space_catalyst_event_state_shadow_summary.json"
UNIVERSE_STATE_PATH = REPO_ROOT / "data" / "universe_state_20260511.json"
SIGNAL_GLOB = "quant_signals_2026*.json"
OUTPUT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260512_103_space_official_primary_source_scout.json"
)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def summarize(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "min": None,
            "max": None,
            "win_rate": None,
        }
    return {
        "count": len(clean),
        "avg": round(sum(clean) / len(clean), 6),
        "median": round(statistics.median(clean), 6),
        "min": round(min(clean), 6),
        "max": round(max(clean), 6),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def load_signal_context() -> dict[str, Any]:
    same_day_ab: set[tuple[str, str]] = set()
    any_day_ab: set[str] = set()
    same_day_core: set[tuple[str, str]] = set()
    any_day_core: set[str] = set()
    files_read = 0

    for path in sorted((REPO_ROOT / "data").glob(SIGNAL_GLOB)):
        try:
            payload = load_json(path)
        except json.JSONDecodeError:
            continue
        files_read += 1
        asof = path.stem.replace("quant_signals_", "")
        asof = f"{asof[:4]}-{asof[4:6]}-{asof[6:]}"
        for key in ("signals", "pilot_signals"):
            for signal in payload.get(key) or []:
                ticker = str(signal.get("ticker") or "").upper()
                strategy = str(signal.get("strategy") or "")
                if not ticker:
                    continue
                any_day_core.add(ticker)
                same_day_core.add((asof, ticker))
                if strategy in {"trend_long", "breakout_long"}:
                    any_day_ab.add(ticker)
                    same_day_ab.add((asof, ticker))

    return {
        "files_read": files_read,
        "same_day_ab": same_day_ab,
        "any_day_ab": any_day_ab,
        "same_day_core": same_day_core,
        "any_day_core": any_day_core,
    }


def registry_context() -> dict[str, Any]:
    if not UNIVERSE_STATE_PATH.exists():
        return {"records": {}, "core_trade_universe": []}
    payload = load_json(UNIVERSE_STATE_PATH)
    return {
        "records": payload.get("records") or {},
        "core_trade_universe": payload.get("core_trade_universe") or [],
        "observation_universe": payload.get("observation_universe") or [],
    }


def row_horizon_metrics(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for horizon, values in (row.get("horizons") or {}).items():
        event_return = finite_number(values.get("event_return"))
        cash_pnl = finite_number(values.get("cash_relative_pnl"))
        same_theme = finite_number(values.get("same_theme_replacement_value"))
        spy_value = finite_number(values.get("spy_relative_value"))
        qqq_value = finite_number(values.get("qqq_relative_value"))
        ufo_value = finite_number(values.get("ufo_relative_value"))
        core_value = finite_number(values.get("core_replacement_value"))
        metrics[horizon] = {
            "event_return": event_return,
            "cash_relative_pnl": cash_pnl,
            "same_theme_replacement_value": same_theme,
            "spy_relative_value": spy_value,
            "qqq_relative_value": qqq_value,
            "ufo_relative_value": ufo_value,
            "core_replacement_value": core_value,
            "core_replacement_value_status": values.get("core_replacement_value_status"),
            "status": values.get("status"),
        }
    return metrics


def main() -> None:
    all_rows = load_jsonl(LEDGER_PATH)
    rows = [row for row in all_rows if row.get("source_type") == SOURCE_TYPE]
    signal_context = load_signal_context()
    registry = registry_context()
    records = registry["records"]

    tickers = sorted({str(row.get("ticker") or "").upper() for row in rows if row.get("ticker")})
    closed_rows = [row for row in rows if row.get("closed_decision")]
    pending_rows = [row for row in rows if not row.get("closed_decision")]
    event_ids = sorted({str(row.get("event_id")) for row in rows})

    horizon_returns: dict[str, list[float]] = {}
    horizon_cash_pnl: dict[str, list[float]] = {}
    horizon_same_theme_value: dict[str, list[float]] = {}
    horizon_spy_value: dict[str, list[float]] = {}
    horizon_core_value: dict[str, list[float]] = {}
    candidate_rows: list[dict[str, Any]] = []

    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        entry_date = str(row.get("entry_date") or "")[:10]
        horizons = row_horizon_metrics(row)
        for horizon, values in horizons.items():
            for target, bucket in [
                ("event_return", horizon_returns),
                ("cash_relative_pnl", horizon_cash_pnl),
                ("same_theme_replacement_value", horizon_same_theme_value),
                ("spy_relative_value", horizon_spy_value),
                ("core_replacement_value", horizon_core_value),
            ]:
                value = values.get(target)
                if value is not None:
                    bucket.setdefault(horizon, []).append(value)
        candidate_rows.append(
            {
                "ticker": ticker,
                "event_id": row.get("event_id"),
                "event_date": row.get("event_date"),
                "entry_date": entry_date,
                "semantic_bucket": row.get("semantic_bucket"),
                "event_fields": row.get("event_fields") or [],
                "source_url": row.get("source_url"),
                "closed_decision": bool(row.get("closed_decision")),
                "outcome_status": row.get("outcome_status"),
                "same_day_ab_overlap": (entry_date, ticker) in signal_context["same_day_ab"],
                "same_day_core_overlap": (entry_date, ticker) in signal_context["same_day_core"],
                "ticker_seen_in_any_ab_signal_file": ticker in signal_context["any_day_ab"],
                "ticker_seen_in_any_signal_file": ticker in signal_context["any_day_core"],
                "same_day_core_alternative_count": row.get("same_day_core_alternative_count"),
                "same_day_core_alternatives": row.get("same_day_core_alternatives") or [],
                "horizons": horizons,
            }
        )

    liquidity = {}
    coverage = {}
    for ticker in tickers:
        meta = records.get(ticker) or {}
        liquidity[ticker] = {
            "liquidity_tier": meta.get("liquidity_tier"),
            "history_class": meta.get("history_class"),
            "status": meta.get("status"),
            "pilot_sleeve": meta.get("pilot_sleeve"),
            "max_capital_scalar": meta.get("max_capital_scalar"),
            "max_risk_scalar": meta.get("max_risk_scalar"),
            "first_trade_allowed_as_of": meta.get("first_trade_allowed_as_of"),
        }
        coverage[ticker] = {
            "in_20260511_universe_state": ticker in records,
            "in_observation_universe": ticker in set(registry.get("observation_universe") or []),
            "in_core_trade_universe": ticker in set(registry.get("core_trade_universe") or []),
        }

    same_day_ab_overlap = sum(1 for row in candidate_rows if row["same_day_ab_overlap"])
    same_day_core_overlap = sum(1 for row in candidate_rows if row["same_day_core_overlap"])
    any_ab_overlap = sum(1 for row in candidate_rows if row["ticker_seen_in_any_ab_signal_file"])
    any_signal_overlap = sum(1 for row in candidate_rows if row["ticker_seen_in_any_signal_file"])

    promotion_blockers = []
    if len(rows) < 10:
        promotion_blockers.append("sample_size_below_10_decisions")
    if len(closed_rows) < 10:
        promotion_blockers.append("closed_forward_decisions_below_10")
    if any(row["horizons"].get("10d", {}).get("core_replacement_value") is None for row in candidate_rows):
        promotion_blockers.append("core_replacement_value_not_available")
    if same_day_ab_overlap == 0:
        promotion_blockers.append("no_same_day_ab_overlap_to_measure_slot_competition")

    summary_payload = load_json(SUMMARY_PATH) if SUMMARY_PATH.exists() else {}
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Space official_or_primary_release event-state rows may be a cleaner "
            "forward shadow source than broad static Space expansion."
        ),
        "change_type": "source_shadow_evaluation",
        "changed_variable": "space official_or_primary_release event-state source",
        "source_filter": {"source_type": SOURCE_TYPE},
        "candidate_count": len(rows),
        "closed_decision_count": len(closed_rows),
        "pending_decision_count": len(pending_rows),
        "unique_event_count": len(event_ids),
        "unique_ticker_count": len(tickers),
        "tickers": tickers,
        "semantic_bucket_counts": dict(Counter(str(row.get("semantic_bucket")) for row in rows)),
        "data_coverage": {
            "ledger_path": str(LEDGER_PATH.relative_to(REPO_ROOT)),
            "summary_path": str(SUMMARY_PATH.relative_to(REPO_ROOT)),
            "ledger_rows_total": len(all_rows),
            "source_rows_total": len(rows),
            "source_rows_with_entry_date": sum(1 for row in rows if row.get("entry_date")),
            "source_rows_with_event_url": sum(1 for row in rows if row.get("source_url")),
            "source_rows_with_horizons": sum(1 for row in rows if row.get("horizons")),
            "signal_files_read": signal_context["files_read"],
            "coverage_by_ticker": coverage,
        },
        "liquidity": liquidity,
        "overlap": {
            "same_day_ab_overlap_count": same_day_ab_overlap,
            "same_day_core_signal_overlap_count": same_day_core_overlap,
            "ticker_seen_in_any_ab_signal_file_count": any_ab_overlap,
            "ticker_seen_in_any_signal_file_count": any_signal_overlap,
        },
        "forward_return_distribution": {
            horizon: summarize(values) for horizon, values in sorted(horizon_returns.items())
        },
        "cash_pnl_distribution": {
            horizon: summarize(values) for horizon, values in sorted(horizon_cash_pnl.items())
        },
        "replacement_value": {
            "same_theme": {
                horizon: summarize(values) for horizon, values in sorted(horizon_same_theme_value.items())
            },
            "spy_relative": {
                horizon: summarize(values) for horizon, values in sorted(horizon_spy_value.items())
            },
            "core": {
                horizon: summarize(values) for horizon, values in sorted(horizon_core_value.items())
            },
            "core_value_available": any(horizon_core_value.values()),
        },
        "scarce_slot_value": {
            "measurable": same_day_ab_overlap > 0 and any(horizon_core_value.values()),
            "same_day_ab_overlap_count": same_day_ab_overlap,
            "same_day_core_alternative_counts": [
                row["same_day_core_alternative_count"] for row in candidate_rows
            ],
            "reason": (
                "No same-day A/B overlap and no closed core replacement values are available"
                if same_day_ab_overlap == 0 or not any(horizon_core_value.values())
                else "Same-day overlap and core replacement values are available"
            ),
        },
        "survivorship_risk_notes": [
            "Rows are forward event-state observations, not a PIT historical universe expansion.",
            "The source has one closed decision in the current ledger, so source quality is underpowered.",
            "Space live slots remain zero; this artifact is source evaluation only.",
            "Static Space pool and GSAT membership expansion remain rejected nearby experiments.",
        ],
        "promotion_eligibility": {
            "eligible": False,
            "reason": "observed_only source scout; promotion requires closed forward replacement value and parity evidence",
            "blockers": promotion_blockers,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "live_slots_changed": False,
            "live_space_slots": 0,
        },
        "baseline_context": {
            "canonical_baseline_file": "data/backtest_results_20260510.json",
            "accepted_core_ev_sum": 6.2882,
            "space_accepted_default_off_stack_ev_sum": 14.0087,
            "summary_active_event_count": summary_payload.get("active_event_count"),
        },
        "rows": candidate_rows,
        "decision": "observed_only",
    }
    write_json(OUTPUT_PATH, payload)
    print(json.dumps({"artifact": str(OUTPUT_PATH), "candidate_count": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
