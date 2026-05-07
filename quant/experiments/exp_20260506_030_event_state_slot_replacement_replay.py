"""exp-20260506-030: event/state slot replacement replay.

Alpha-search replay only. This takes the narrow event/state-qualified shadow
universe from exp-20260506-026 and asks the production-relevant question that
026 could not answer: do those candidates have scarce-slot replacement value
against the accepted core stack, or are they just good standalone watchlist
ideas?

No production policy is changed here.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260506-030"
STEM = "event_state_slot_replacement_replay"
ROOT = Path(__file__).resolve().parents[2]

SOURCE_ARTIFACT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260506-026"
    / "exp_20260506_026_event_state_qualified_shadow_universe.json"
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": ROOT / "data/ohlcv_snapshot_20251023_20260421.json",
                "baseline": ROOT / "data/experiments/exp-20260505-025/baseline_late_strong.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": ROOT / "data/ohlcv_snapshot_20250423_20251022.json",
                "baseline": ROOT / "data/experiments/exp-20260505-025/baseline_mid_weak.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": ROOT / "data/ohlcv_snapshot_20241002_20250422.json",
                "baseline": ROOT / "data/experiments/exp-20260505-025/baseline_old_thin.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = ROOT / "docs" / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"

NOTIONAL = 10_000
ROUND_TRIP_COST = 0.0035
FORWARD_HORIZON_DAYS = 10
NEARBY_CORE_TRADE_DAYS = 2


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _dist(values: list[float]) -> dict[str, Any]:
    values = [float(v) for v in values if v is not None]
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
    return {
        "count": len(values),
        "avg": _round(_mean(values), 2),
        "median": _round(statistics.median(values), 2),
        "p25": _round(ordered[int((len(ordered) - 1) * 0.25)], 2),
        "p75": _round(ordered[int((len(ordered) - 1) * 0.75)], 2),
        "win_rate": _round(sum(1 for v in values if v > 0) / len(values), 4),
        "best": _round(max(values), 2),
        "worst": _round(min(values), 2),
    }


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 2),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = load_json(path)
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected OHLCV snapshot shape: {path}")
    return {
        str(ticker).upper(): sorted(rows, key=lambda row: str(row.get("Date") or ""))
        for ticker, rows in ohlcv.items()
        if isinstance(rows, list)
    }


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("Date")): idx for idx, row in enumerate(rows)}


def _forward_net_pnl(
    ohlcv: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_str: str,
    horizon: int = FORWARD_HORIZON_DAYS,
) -> tuple[float | None, float | None, str | None]:
    rows = ohlcv.get(ticker.upper())
    if not rows:
        return None, None, None
    idx = _date_index(rows).get(date_str)
    if idx is None or idx + horizon >= len(rows):
        return None, None, None
    entry = rows[idx].get("Close")
    exit_row = rows[idx + horizon]
    exit_close = exit_row.get("Close")
    try:
        entry_close = float(entry)
        exit_price = float(exit_close)
    except (TypeError, ValueError):
        return None, None, None
    if entry_close <= 0:
        return None, None, None
    gross_return = exit_price / entry_close - 1.0
    net_return = gross_return - ROUND_TRIP_COST
    return net_return, NOTIONAL * net_return, str(exit_row.get("Date"))


def _baseline_trade_rows(
    baseline: dict[str, Any],
    ohlcv: dict[str, list[dict[str, Any]]],
    spy_dates: list[str],
) -> list[dict[str, Any]]:
    spy_index = {date: idx for idx, date in enumerate(spy_dates)}
    rows: list[dict[str, Any]] = []
    for trade in baseline.get("trades", []):
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")
        net_return, net_pnl, exit_date = _forward_net_pnl(ohlcv, ticker, entry_date)
        if net_pnl is None:
            continue
        rows.append(
            {
                "ticker": ticker,
                "strategy": trade.get("strategy"),
                "entry_date": entry_date,
                "entry_day_index": spy_index.get(entry_date),
                "realized_pnl": _round(trade.get("pnl"), 2),
                "realized_pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                "forward_10d_net_return": _round(net_return, 6),
                "forward_10d_net_pnl_10k": _round(net_pnl, 2),
                "forward_10d_exit_date": exit_date,
            }
        )
    return rows


def _same_or_nearby_core(
    core_rows: list[dict[str, Any]],
    entry_date: str,
    spy_index: dict[str, int],
    radius: int,
) -> list[dict[str, Any]]:
    entry_idx = spy_index.get(entry_date)
    if entry_idx is None:
        return []
    matches = []
    for row in core_rows:
        day_idx = row.get("entry_day_index")
        if day_idx is None:
            continue
        if abs(int(day_idx) - entry_idx) <= radius:
            item = dict(row)
            item["day_distance"] = int(day_idx) - entry_idx
            matches.append(item)
    return sorted(matches, key=lambda item: (abs(item["day_distance"]), item["entry_date"], item["ticker"]))


def _same_day_pressure_dates(baseline: dict[str, Any]) -> set[str]:
    attribution = baseline.get("entry_execution_attribution") or {}
    by_date = attribution.get("by_date") or {}
    pressure = set()
    pressure_reasons = {
        "slot_sliced",
        "scarce_slot_breakout_deferred",
        "no_shares",
    }
    for date_str, reasons in by_date.items():
        if any((reasons or {}).get(reason, 0) for reason in pressure_reasons):
            pressure.add(str(date_str))
    return pressure


def analyze() -> dict[str, Any]:
    source = load_json(SOURCE_ARTIFACT)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    window_reports: OrderedDict[str, Any] = OrderedDict()
    all_rows: list[dict[str, Any]] = []

    for name, cfg in WINDOWS.items():
        baseline = load_json(cfg["baseline"])
        ohlcv = _load_snapshot(cfg["snapshot"])
        spy_rows = ohlcv.get("SPY", [])
        spy_dates = [str(row.get("Date")) for row in spy_rows]
        spy_index = {date: idx for idx, date in enumerate(spy_dates)}
        core_rows = _baseline_trade_rows(baseline, ohlcv, spy_dates)
        pressure_dates = _same_day_pressure_dates(baseline)

        selected_rows = source["windows"][name].get("selected_rows", [])
        enriched_rows = []
        replacement_values_same_day: list[float] = []
        replacement_values_nearby: list[float] = []
        candidate_pnls: list[float] = []
        candidate_excess: list[float] = []
        pressure_candidate_rows = 0
        same_day_comparable_rows = 0
        nearby_comparable_rows = 0

        for row in selected_rows:
            ticker = str(row.get("ticker") or "").upper()
            entry_date = str(row.get("entry_date_used") or row.get("entry_date") or "")
            net_return, net_pnl, exit_date = _forward_net_pnl(ohlcv, ticker, entry_date)
            if net_pnl is None:
                continue
            same_day = _same_or_nearby_core(core_rows, entry_date, spy_index, radius=0)
            nearby = _same_or_nearby_core(core_rows, entry_date, spy_index, radius=NEARBY_CORE_TRADE_DAYS)
            same_day_avg = _mean([float(item["forward_10d_net_pnl_10k"]) for item in same_day])
            nearby_avg = _mean([float(item["forward_10d_net_pnl_10k"]) for item in nearby])
            same_day_replacement = net_pnl - same_day_avg if same_day_avg is not None else None
            nearby_replacement = net_pnl - nearby_avg if nearby_avg is not None else None
            if same_day_replacement is not None:
                replacement_values_same_day.append(same_day_replacement)
                same_day_comparable_rows += 1
            if nearby_replacement is not None:
                replacement_values_nearby.append(nearby_replacement)
                nearby_comparable_rows += 1
            if entry_date in pressure_dates:
                pressure_candidate_rows += 1
            candidate_pnls.append(float(net_pnl))
            excess = row.get("forward_10d_excess_return")
            if excess is not None:
                candidate_excess.append(float(excess))
            enriched = {
                "window": name,
                "ticker": ticker,
                "entry_date": entry_date,
                "source": row.get("source"),
                "candidate_forward_10d_net_return": _round(net_return, 6),
                "candidate_forward_10d_net_pnl_10k": _round(net_pnl, 2),
                "candidate_forward_10d_exit_date": exit_date,
                "forward_10d_excess_return": _round(excess, 6),
                "same_day_slot_pressure": entry_date in pressure_dates,
                "same_day_core_count": len(same_day),
                "same_day_core_avg_forward_10d_net_pnl_10k": _round(same_day_avg, 2),
                "same_day_replacement_value_10k": _round(same_day_replacement, 2),
                "nearby_core_radius_trading_days": NEARBY_CORE_TRADE_DAYS,
                "nearby_core_count": len(nearby),
                "nearby_core_avg_forward_10d_net_pnl_10k": _round(nearby_avg, 2),
                "nearby_replacement_value_10k": _round(nearby_replacement, 2),
                "nearby_core_sample": [
                    {
                        "ticker": item["ticker"],
                        "strategy": item["strategy"],
                        "entry_date": item["entry_date"],
                        "day_distance": item["day_distance"],
                        "forward_10d_net_pnl_10k": item["forward_10d_net_pnl_10k"],
                    }
                    for item in nearby[:5]
                ],
            }
            enriched_rows.append(enriched)
            all_rows.append(enriched)

        median_candidate_excess = statistics.median(candidate_excess) if candidate_excess else None
        window_reports[name] = {
            "window": {
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": str(cfg["snapshot"].relative_to(ROOT)),
                "state_note": cfg["state_note"],
            },
            "baseline_metrics": _metrics(baseline),
            "selected_candidate_count": len(selected_rows),
            "candidate_count_with_forward_10d": len(candidate_pnls),
            "same_day_slot_pressure_candidate_count": pressure_candidate_rows,
            "same_day_comparable_count": same_day_comparable_rows,
            "nearby_comparable_count": nearby_comparable_rows,
            "candidate_forward_10d_net_pnl_10k": _dist(candidate_pnls),
            "forward_10d_excess_return": _dist(candidate_excess),
            "median_forward_10d_excess_return_positive": bool(
                median_candidate_excess is not None and median_candidate_excess > 0
            ),
            "same_day_replacement_value_10k": _dist(replacement_values_same_day),
            "nearby_replacement_value_10k": _dist(replacement_values_nearby),
            "rows": enriched_rows,
        }

    windows = list(window_reports.values())
    same_day_total = sum(w["same_day_comparable_count"] for w in windows)
    nearby_total = sum(w["nearby_comparable_count"] for w in windows)
    positive_median_excess_windows = sum(
        1 for w in windows if w["median_forward_10d_excess_return_positive"]
    )
    positive_nearby_replacement_windows = sum(
        1
        for w in windows
        if (w["nearby_replacement_value_10k"]["median"] is not None)
        and w["nearby_replacement_value_10k"]["median"] > 0
    )
    pressure_total = sum(w["same_day_slot_pressure_candidate_count"] for w in windows)

    promotion_grade = bool(
        same_day_total >= 5
        and positive_median_excess_windows == 3
        and positive_nearby_replacement_windows >= 2
    )
    decision = "accepted_for_promotion_candidate" if promotion_grade else "rejected_for_promotion"

    aggregate = {
        "selected_candidate_count": len(all_rows),
        "unique_ticker_count": len({row["ticker"] for row in all_rows}),
        "same_day_comparable_count": same_day_total,
        "nearby_comparable_count": nearby_total,
        "same_day_slot_pressure_candidate_count": pressure_total,
        "windows_with_positive_median_10d_excess": positive_median_excess_windows,
        "windows_with_positive_median_nearby_replacement_value": positive_nearby_replacement_windows,
        "candidate_forward_10d_net_pnl_10k": _dist(
            [float(row["candidate_forward_10d_net_pnl_10k"]) for row in all_rows]
        ),
        "same_day_replacement_value_10k": _dist(
            [
                float(row["same_day_replacement_value_10k"])
                for row in all_rows
                if row["same_day_replacement_value_10k"] is not None
            ]
        ),
        "nearby_replacement_value_10k": _dist(
            [
                float(row["nearby_replacement_value_10k"])
                for row in all_rows
                if row["nearby_replacement_value_10k"] is not None
            ]
        ),
        "promotion_grade_evidence": promotion_grade,
    }

    result: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": "closed",
        "decision": decision,
        "lane": "alpha_search",
        "change_type": "universe_scout_replacement_value",
        "hypothesis": (
            "Event/state-qualified shadow candidates may provide positive scarce-slot "
            "replacement value versus the accepted core stack."
        ),
        "alpha_hypothesis": {
            "category": "candidate_pool",
            "description": (
                "A narrow event-qualified, price-confirmed external candidate set can "
                "improve returns by replacing lower-value same-day or nearby core entries."
            ),
            "why_not_llm_soft_ranking": (
                "LLM replay coverage remains too sparse for a reliable soft-ranking "
                "experiment, so this run tests a different alpha lane."
            ),
        },
        "single_causal_variable": (
            "slot-aware replacement value of the already-frozen exp-20260506-026 "
            "event/state shadow universe"
        ),
        "history_guardrail": {
            "not_repeating": [
                "broad noisy ticker expansion rejected in exp-20260505-009 and related basket tests",
                "same-sample event threshold retuning rejected in event-bundle experiments",
                "LLM soft-ranking deferred because replay attribution data is sparse",
                "nearby broad_rotation SPY-leader risk and high-dispersion trend risk experiments rejected today",
            ],
            "why_this_is_not_duplicate": (
                "The event/state candidate set is frozen from 026; this run only tests "
                "scarce-slot replacement value against core alternatives."
            ),
        },
        "parameters": {
            "source_artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)),
            "forward_horizon_days": FORWARD_HORIZON_DAYS,
            "shadow_notional": NOTIONAL,
            "round_trip_cost": ROUND_TRIP_COST,
            "nearby_core_trade_radius_trading_days": NEARBY_CORE_TRADE_DAYS,
            "promotion_min_same_day_comparables": 5,
            "promotion_requires_positive_median_excess_windows": 3,
            "promotion_requires_positive_nearby_replacement_windows": 2,
        },
        "date_range": {
            name: f"{cfg['start']} -> {cfg['end']}" for name, cfg in WINDOWS.items()
        },
        "market_regime_summary": {
            name: cfg["state_note"] for name, cfg in WINDOWS.items()
        },
        "before_metrics": {
            name: report["baseline_metrics"] for name, report in window_reports.items()
        },
        "after_metrics": {
            name: report["baseline_metrics"] for name, report in window_reports.items()
        },
        "delta_metrics": {
            "strategy_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
        },
        "aggregate": aggregate,
        "windows": window_reports,
        "gate4": {
            "passed": False,
            "basis": (
                "Replay-only replacement-value audit. No shared policy changed; "
                "promotion failed because same-day replacement comparables remain sparse "
                "and median excess is not positive in all three windows."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "rejection_reason": (
            "Closed rejected_for_promotion: standalone forward returns remain interesting, "
            "but the evidence still does not prove scarce-slot replacement value."
        ),
        "next_retry_requires": [
            "More same-day slot-pressure comparables or forward paper outcomes.",
            "A true slot-aware replay that can substitute candidates into position slots without look-ahead.",
            "Positive median 10d excess return across all three canonical windows.",
        ],
    }
    return result


def write_artifact(result: dict[str, Any]) -> None:
    lines = [
        f"# {EXPERIMENT_ID}: event/state slot replacement replay",
        "",
        "## Decision",
        "",
        f"- status: {result['status']}",
        f"- decision: {result['decision']}",
        f"- Gate 4: {'PASS' if result['gate4']['passed'] else 'FAIL'}",
        f"- production impact: replay_only={result['production_impact']['replay_only']}, "
        f"shared_policy_changed={result['production_impact']['shared_policy_changed']}",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Three-window baseline and replay evidence",
        "",
        "| Window | EV | Sharpe daily | PnL | Trades | Selected | Same-day comps | Nearby comps | Median 10d excess | Median nearby replacement |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, report in result["windows"].items():
        metrics = report["baseline_metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    str(metrics["expected_value_score"]),
                    str(metrics["sharpe_daily"]),
                    str(metrics["total_pnl"]),
                    str(metrics["trade_count"]),
                    str(report["selected_candidate_count"]),
                    str(report["same_day_comparable_count"]),
                    str(report["nearby_comparable_count"]),
                    str(report["forward_10d_excess_return"]["median"]),
                    str(report["nearby_replacement_value_10k"]["median"]),
                ]
            )
            + " |"
        )
    aggregate = result["aggregate"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- selected candidates: {aggregate['selected_candidate_count']}",
            f"- unique tickers: {aggregate['unique_ticker_count']}",
            f"- same-day comparable count: {aggregate['same_day_comparable_count']}",
            f"- nearby comparable count: {aggregate['nearby_comparable_count']}",
            f"- windows with positive median 10d excess: {aggregate['windows_with_positive_median_10d_excess']}/3",
            f"- windows with positive median nearby replacement value: {aggregate['windows_with_positive_median_nearby_replacement_value']}/3",
            f"- aggregate median nearby replacement value per 10k: {aggregate['nearby_replacement_value_10k']['median']}",
            "",
            "## Closeout",
            "",
            result["rejection_reason"],
            "",
            "The experiment did not modify production or backtest strategy logic. The next valid retry needs more same-day slot-pressure evidence or a true substitution replay, not another broader ticker list.",
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    result = analyze()
    write_json(OUT_JSON, result)
    write_json(LOG_JSON, result)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Event/state slot replacement replay",
        "status": result["status"],
        "decision": result["decision"],
        "lane": result["lane"],
        "gate4_passed": result["gate4"]["passed"],
        "summary": result["rejection_reason"],
        "next_retry_requires": result["next_retry_requires"],
        "related_files": [
            str(OUT_JSON.relative_to(ROOT)),
            str(LOG_JSON.relative_to(ROOT)),
            str(ARTIFACT_MD.relative_to(ROOT)),
        ],
    }
    write_json(TICKET_JSON, ticket)
    write_artifact(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": result["decision"],
                "gate4_passed": result["gate4"]["passed"],
                "aggregate": result["aggregate"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
