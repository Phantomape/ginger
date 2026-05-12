"""exp-20260511-103 official-catalyst shadow universe refresh.

Observed-only universe scout. This script audits the existing official-catalyst
shadow universe evidence without changing production universe membership,
signal generation, sizing, ranking, exits, or order routing.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

EXPERIMENT_ID = "exp-20260511-103"
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260511_103_official_catalyst_shadow_universe_refresh.json"
)

BASELINE_FILE = REPO_ROOT / "data" / "experiments" / "exp-20260510-015" / "trip_sector_taxonomy.json"
SPACE_BUILD_FILE = (
    REPO_ROOT / "data" / "experiments" / "exp-20260510-028" / "space_catalyst_ohlcv_snapshot_build.json"
)
SPACE_FORWARD_LEDGER = (
    REPO_ROOT / "data" / "experiments" / "exp-20260511-008" / "space_event_state_shadow.json"
)
ACCEPTED_SPACE_STACK_FILE = (
    REPO_ROOT / "data" / "experiments" / "exp-20260511-032" / "space_trend_target_extension.json"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "core_snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "augmented_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_late_strong_with_space_catalyst.json"
        ),
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "core_snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "augmented_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_mid_weak_with_space_catalyst.json"
        ),
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "core_snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "augmented_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_old_thin_with_space_catalyst.json"
        ),
    },
}

OFFICIAL_CATALYST_TICKERS = ("RKLB", "ASTS", "LUNR", "PL", "RDW", "BKSY")
UNAVAILABLE_OFFICIAL_CATALYST_TICKERS = {"HAWK": "no rows in exp-20260510-028 snapshots"}
EXCLUDED_PRIOR_REJECTED = {
    "IRDM": "mature satcom breadth rejected by exp-20260511-026",
    "VSAT": "mature satcom breadth rejected by exp-20260511-026",
    "SATS": "mature satcom breadth rejected by exp-20260511-026",
    "GSAT": "not in accepted official-catalyst operating sleeve",
    "SPCE": "quarantine / meme dilution risk",
    "ARKX": "theme ETF proxy, not operating company universe",
    "UFO": "theme ETF proxy, not operating company universe",
}
FORWARD_HORIZONS = (5, 10, 20)
SHADOW_NOTIONAL = 10_000.0


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def distribution(values: list[float | None]) -> dict[str, Any]:
    clean = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not clean:
        return {
            "count": 0,
            "avg_pct": None,
            "median_pct": None,
            "p25_pct": None,
            "p75_pct": None,
            "win_rate": None,
            "best_pct": None,
            "worst_pct": None,
        }
    return {
        "count": len(clean),
        "avg_pct": round(mean(clean) * 100, 4),
        "median_pct": round(statistics.median(clean) * 100, 4),
        "p25_pct": round(clean[int((len(clean) - 1) * 0.25)] * 100, 4),
        "p75_pct": round(clean[int((len(clean) - 1) * 0.75)] * 100, 4),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "best_pct": round(max(clean) * 100, 4),
        "worst_pct": round(min(clean) * 100, 4),
    }


def rows_by_date(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("Date"))[:10]: idx for idx, row in enumerate(rows or [])}


def close_map(rows: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for row in rows or []:
        try:
            close = float(row["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if close > 0:
            result[str(row.get("Date"))[:10]] = close
    return result


def window_dates(snapshot: dict[str, Any], start: str, end: str) -> list[str]:
    spy = close_map((snapshot.get("ohlcv") or {}).get("SPY", []))
    return [date for date in sorted(spy) if start <= date <= end]


def coverage(rows: list[dict[str, Any]], dates: list[str]) -> float:
    available = set(close_map(rows))
    return len([date for date in dates if date in available]) / len(dates) if dates else 0.0


def median_dollar_volume(rows: list[dict[str, Any]], start: str, end: str) -> float | None:
    values: list[float] = []
    for row in rows or []:
        date = str(row.get("Date"))[:10]
        if not (start <= date <= end):
            continue
        try:
            values.append(float(row["Close"]) * float(row["Volume"]))
        except (KeyError, TypeError, ValueError):
            continue
    return median(values)


def forward_return(rows: list[dict[str, Any]], entry_date: str, horizon: int) -> float | None:
    index = rows_by_date(rows)
    if entry_date not in index:
        return None
    idx = index[entry_date]
    if idx + horizon >= len(rows):
        return None
    try:
        entry = float(rows[idx]["Open"])
        exit_close = float(rows[idx + horizon]["Close"])
    except (KeyError, TypeError, ValueError):
        return None
    if entry <= 0:
        return None
    return exit_close / entry - 1.0


def monthly_probe_dates(dates: list[str]) -> list[str]:
    seen_months: set[str] = set()
    probes: list[str] = []
    for date in dates:
        month = date[:7]
        if month in seen_months:
            continue
        seen_months.add(month)
        probes.append(date)
    return probes


def load_core_universe() -> set[str]:
    tickers: set[str] = set()
    try:
        from data_layer import get_universe  # type: ignore

        tickers.update(str(ticker).upper() for ticker in get_universe())
    except Exception:
        pass
    registry = REPO_ROOT / "data" / "universe_registry.json"
    if registry.exists():
        payload = load_json(registry)
        for ticker, meta in (payload.get("tickers") or {}).items():
            if (meta or {}).get("status") in {"core", "limited_production", "specialist", "pilot"}:
                tickers.add(str(ticker).upper())
    return tickers


def baseline_trade_context() -> dict[str, Any]:
    payload = load_json(BASELINE_FILE)
    same_day: set[tuple[str, str]] = set()
    ticker_history: set[str] = set()
    pnl_by_day: dict[str, list[float]] = defaultdict(list)
    for window in (payload.get("by_window") or {}).values():
        for trade in window.get("after_metrics", {}).get("trades", []) or []:
            ticker = str(trade.get("ticker") or "").upper()
            date = str(trade.get("entry_date") or "")[:10]
            if ticker and date:
                same_day.add((date, ticker))
                ticker_history.add(ticker)
                pnl_by_day[date].append(float(trade.get("pnl") or 0.0))
        for changed in window.get("changed_trades", []) or []:
            trade = changed.get("after") or {}
            ticker = str(trade.get("ticker") or "").upper()
            date = str(trade.get("entry_date") or "")[:10]
            if ticker and date:
                same_day.add((date, ticker))
                ticker_history.add(ticker)
                pnl_by_day[date].append(float(trade.get("pnl") or 0.0))
    return {"same_day": same_day, "ticker_history": ticker_history, "pnl_by_day": pnl_by_day}


def baseline_metrics() -> dict[str, dict[str, Any]]:
    payload = load_json(BASELINE_FILE)
    return {
        label: dict(window.get("after_metrics") or {})
        for label, window in (payload.get("by_window") or {}).items()
    }


def accepted_space_trade_evidence() -> dict[str, Any]:
    if not ACCEPTED_SPACE_STACK_FILE.exists():
        return {"available": False}
    payload = load_json(ACCEPTED_SPACE_STACK_FILE)
    best = payload.get("best_variant") or {}
    return {
        "available": True,
        "source": str(ACCEPTED_SPACE_STACK_FILE.relative_to(REPO_ROOT)),
        "decision": payload.get("decision"),
        "accepted_stack_aggregate": {
            "expected_value_score_sum": (payload.get("after_aggregate") or {}).get("expected_value_score_sum"),
            "total_pnl_sum": (payload.get("after_aggregate") or {}).get("total_pnl_sum"),
            "max_drawdown_pct_max": (payload.get("after_aggregate") or {}).get("max_drawdown_pct_max"),
            "trade_count_sum": (payload.get("after_aggregate") or {}).get("trade_count_sum"),
        },
        "space_trade_attribution": best.get("space_trade_attribution"),
        "space_trend_trade_attribution": best.get("space_trend_trade_attribution"),
        "note": "Accepted default-off evidence, not live universe promotion.",
    }


def event_forward_evidence() -> dict[str, Any]:
    if not SPACE_FORWARD_LEDGER.exists():
        return {"available": False}
    payload = load_json(SPACE_FORWARD_LEDGER)
    return {
        "available": True,
        "source": str(SPACE_FORWARD_LEDGER.relative_to(REPO_ROOT)),
        "event_count": (payload.get("aggregate") or {}).get("event_count"),
        "mature_event_count": (payload.get("aggregate") or {}).get("mature_event_count"),
        "pending_event_count": (payload.get("aggregate") or {}).get("pending_event_count"),
        "overall": (payload.get("aggregate") or {}).get("overall"),
        "by_semantic_bucket": (payload.get("aggregate") or {}).get("by_semantic_bucket"),
        "promotion_gate_status": "insufficient_mature_forward_evidence",
    }


def analyze_window(
    label: str,
    spec: dict[str, str],
    core_universe: set[str],
    trade_context: dict[str, Any],
) -> dict[str, Any]:
    core_snapshot = load_json(REPO_ROOT / spec["core_snapshot"])
    augmented_snapshot = load_json(REPO_ROOT / spec["augmented_snapshot"])
    core_ohlcv = core_snapshot.get("ohlcv") or {}
    augmented_ohlcv = augmented_snapshot.get("ohlcv") or {}
    dates = window_dates(augmented_snapshot, spec["start"], spec["end"])
    probes = monthly_probe_dates(dates)

    ticker_rows: dict[str, Any] = {}
    candidate_events: list[dict[str, Any]] = []
    for ticker in OFFICIAL_CATALYST_TICKERS:
        rows = augmented_ohlcv.get(ticker) or []
        ticker_cov = coverage(rows, dates)
        med_dv = median_dollar_volume(rows, spec["start"], spec["end"])
        in_core_snapshot = ticker in core_ohlcv
        ticker_rows[ticker] = {
            "in_core_snapshot": in_core_snapshot,
            "in_augmented_snapshot": bool(rows),
            "in_core_or_pilot_universe": ticker in core_universe,
            "coverage_fraction": round(ticker_cov, 4),
            "median_dollar_volume": round(med_dv, 2) if med_dv is not None else None,
            "liquidity_ready": bool(ticker_cov >= 0.95 and med_dv is not None and med_dv >= 10_000_000),
        }
        for entry_date in probes:
            if entry_date not in rows_by_date(rows):
                continue
            event = {
                "ticker": ticker,
                "entry_date": entry_date,
                "same_day_core_overlap": (entry_date, ticker) in trade_context["same_day"],
                "ticker_seen_in_core_history": ticker in trade_context["ticker_history"],
                "in_core_or_pilot_universe": ticker in core_universe,
            }
            for horizon in FORWARD_HORIZONS:
                ret = forward_return(rows, entry_date, horizon)
                event[f"forward_{horizon}d_return"] = round(ret, 6) if ret is not None else None
                event[f"shadow_{horizon}d_pnl"] = (
                    round(ret * SHADOW_NOTIONAL, 2) if ret is not None else None
                )
            same_day_core = trade_context["pnl_by_day"].get(entry_date) or []
            if same_day_core and event.get("shadow_10d_pnl") is not None:
                event["replacement_value_vs_same_day_core_avg_pnl"] = round(
                    event["shadow_10d_pnl"] - (sum(same_day_core) / len(same_day_core)),
                    2,
                )
            candidate_events.append(event)

    outside_core_events = [row for row in candidate_events if not row["in_core_or_pilot_universe"]]
    replacement_values = [
        row.get("replacement_value_vs_same_day_core_avg_pnl")
        for row in candidate_events
        if row.get("replacement_value_vs_same_day_core_avg_pnl") is not None
    ]
    return {
        "window": label,
        "start": spec["start"],
        "end": spec["end"],
        "core_snapshot": spec["core_snapshot"],
        "augmented_snapshot": spec["augmented_snapshot"],
        "trading_days": len(dates),
        "monthly_probe_count": len(probes),
        "candidate_count": len(candidate_events),
        "unique_candidate_tickers": sorted({row["ticker"] for row in candidate_events}),
        "ticker_coverage": ticker_rows,
        "same_day_core_overlap_rate": round(
            sum(1 for row in candidate_events if row["same_day_core_overlap"]) / len(candidate_events),
            4,
        )
        if candidate_events
        else None,
        "ticker_history_core_overlap_rate": round(
            sum(1 for row in candidate_events if row["ticker_seen_in_core_history"]) / len(candidate_events),
            4,
        )
        if candidate_events
        else None,
        "outside_core_or_pilot_candidate_count": len(outside_core_events),
        "outside_core_or_pilot_unique_tickers": sorted({row["ticker"] for row in outside_core_events}),
        "forward_return_distribution": {
            f"{horizon}d": distribution([row.get(f"forward_{horizon}d_return") for row in candidate_events])
            for horizon in FORWARD_HORIZONS
        },
        "outside_core_forward_return_distribution": {
            f"{horizon}d": distribution([row.get(f"forward_{horizon}d_return") for row in outside_core_events])
            for horizon in FORWARD_HORIZONS
        },
        "scarce_slot_replacement_proxy": {
            "comparable_same_day_core_count": len(replacement_values),
            "avg_10d_shadow_pnl_vs_same_day_core_avg_pnl": (
                round(sum(replacement_values) / len(replacement_values), 2)
                if replacement_values
                else None
            ),
            "note": "Monthly-probe proxy only; not a slot-aware portfolio replay.",
        },
        "candidates": candidate_events,
        "sample_candidates": candidate_events[:30],
    }


def aggregate_windows(windows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    all_rows = [row for window in windows.values() for row in window["candidates"]]
    outside_rows = [row for row in all_rows if not row["in_core_or_pilot_universe"]]
    positive_10d_windows = sum(
        1
        for window in windows.values()
        if (window["forward_return_distribution"]["10d"]["avg_pct"] or 0.0) > 0
    )
    return {
        "candidate_count": sum(window["candidate_count"] for window in windows.values()),
        "unique_candidate_ticker_count": len({row["ticker"] for row in all_rows}),
        "outside_core_or_pilot_candidate_count": len(outside_rows),
        "outside_core_or_pilot_unique_tickers": sorted({row["ticker"] for row in outside_rows}),
        "windows_with_positive_avg_10d_return": positive_10d_windows,
        "forward_return_distribution": {
            f"{horizon}d": distribution([row.get(f"forward_{horizon}d_return") for row in all_rows])
            for horizon in FORWARD_HORIZONS
        },
        "outside_core_forward_return_distribution": {
            f"{horizon}d": distribution([row.get(f"forward_{horizon}d_return") for row in outside_rows])
            for horizon in FORWARD_HORIZONS
        },
    }


def run() -> dict[str, Any]:
    core_universe = load_core_universe()
    trade_context = baseline_trade_context()
    windows = {
        label: analyze_window(label, spec, core_universe, trade_context)
        for label, spec in WINDOWS.items()
    }
    aggregate = aggregate_windows(windows)
    build_payload = load_json(SPACE_BUILD_FILE) if SPACE_BUILD_FILE.exists() else {}
    baseline = baseline_metrics()
    promotion_ready = (
        aggregate["outside_core_or_pilot_candidate_count"] > 0
        and aggregate["windows_with_positive_avg_10d_return"] == len(WINDOWS)
        and (event_forward_evidence().get("mature_event_count") or 0) >= 10
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "universe_scout",
        "status": "observed_only",
        "decision": "observed_only_no_promotion",
        "hypothesis": (
            "An official-catalyst event-sensitive shadow universe can produce "
            "non-overlapping candidates with measurable closed forward value "
            "without adding production tickers."
        ),
        "change_type": "universe_expansion",
        "single_causal_variable": "official-catalyst shadow universe refresh",
        "baseline_result_file": str(BASELINE_FILE.relative_to(REPO_ROOT)),
        "expected_value_score": None,
        "sharpe_daily": None,
        "max_drawdown_pct": None,
        "win_rate": None,
        "survival_rate": None,
        "total_pnl": None,
        "benchmarks": {"strategy_total_return_pct": None},
        "parameters": {
            "official_catalyst_tickers": list(OFFICIAL_CATALYST_TICKERS),
            "unavailable_official_tickers": UNAVAILABLE_OFFICIAL_CATALYST_TICKERS,
            "excluded_prior_rejected": EXCLUDED_PRIOR_REJECTED,
            "forward_horizons": list(FORWARD_HORIZONS),
            "shadow_notional": SHADOW_NOTIONAL,
            "probe_mode": "first_trading_day_of_each_month_per_ticker",
            "locked_variables": ["official-catalyst shadow universe refresh"],
        },
        "historical_constraints": {
            "prior_event_sensitive_scouts": [
                "exp-20260427-005: clean-news coverage sparse outside late window.",
                "exp-20260509-023: broad event-sensitive universe had no external production/pilot candidates.",
            ],
            "space_guardrails": [
                "exp-20260511-011 accepted only a default-off forward Space official-catalyst hypothesis.",
                "exp-20260511-026 rejected mature-satcom breadth.",
                "exp-20260511-030 rejected theme ETF timing gate.",
                "exp-20260511-037 rejected Space breakout target extension.",
                "exp-20260511-038 rejected Space trend-target bucket narrowing.",
            ],
        },
        "baseline_metrics_by_window": baseline,
        "source_snapshot_build": {
            "source": str(SPACE_BUILD_FILE.relative_to(REPO_ROOT)),
            "tickers_requested": build_payload.get("tickers_requested"),
            "notes": build_payload.get("notes"),
        },
        "aggregate": {
            **aggregate,
            "promotion_ready": promotion_ready,
            "promotion_blockers": [
                "No production universe change is allowed by ticket.",
                "Forward event ledger has fewer than 10 mature closed decisions.",
                "Official-catalyst names are already handled as default-off Space shadow metadata, not live slots.",
            ],
        },
        "windows": windows,
        "accepted_default_off_space_evidence": accepted_space_trade_evidence(),
        "forward_event_evidence": event_forward_evidence(),
        "survivorship_and_pit_risk": {
            "risk": "medium_high",
            "reasons": [
                "The Space candidate list was defined after historical windows, so older-window returns are shadow evidence, not PIT universe-discovery proof.",
                "Augmented OHLCV snapshots were fetched after the fact and exclude unavailable recent names such as HAWK.",
                "Forward official-catalyst event evidence currently has too few mature closed decisions for promotion.",
            ],
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
            "production_universe_changed": False,
        },
        "decision_rationale": (
            "Observed-only. The refreshed official-catalyst shadow universe remains "
            "interesting as default-off forward metadata, but mature forward evidence "
            "is insufficient and this ticket does not permit production promotion."
        ),
        "related_files": [
            "quant/experiments/exp_20260511_103_official_catalyst_shadow_universe_refresh.py",
            "data/experiments/exp-20260511-103/exp_20260511_103_official_catalyst_shadow_universe_refresh.json",
        ],
    }


def main() -> None:
    payload = run()
    write_json(OUT_JSON, payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "output": str(OUT_JSON.relative_to(REPO_ROOT)),
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
