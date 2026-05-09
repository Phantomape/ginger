"""Measure a narrow AI-infrastructure RS-breakout shadow universe.

This is a universe scout artifact only. It does not add tickers to production
or alter signal, risk, backtest, or run-path behavior.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260508-031"
OUTPUT_PATH = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260508_031_ai_infra_rs_breakout_shadow.json"
)
BACKTEST_RESULT = REPO_ROOT / "data" / "backtest_results_20260508.json"
UNIVERSE_REGISTRY = REPO_ROOT / "data" / "universe_registry.json"

WINDOWS = [
    {
        "name": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
    },
    {
        "name": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
    },
    {
        "name": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
    },
]

SHADOW_TICKERS = ["BE", "INTC", "LITE"]
BENCHMARK = "QQQ"
LOOKBACK_DAYS = 20
MIN_DOLLAR_VOLUME_20D = 20_000_000
MIN_RS20_VS_QQQ = 0.05
MIN_CLOSE = 10.0
COOLDOWN_DAYS = 10
FORWARD_HORIZONS = [5, 10, 20]
SCARCE_SLOT_DECISIONS = {"scarce_slot_breakout_deferred", "slot_sliced"}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def parse_day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def pct_change(end_value: float | None, start_value: float | None) -> float | None:
    if end_value is None or start_value in (None, 0):
        return None
    return (end_value / start_value) - 1.0


def summarize(values: list[float]) -> dict[str, Any]:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return {"count": 0}
    wins = [v for v in clean if v > 0]
    return {
        "count": len(clean),
        "mean": round(mean(clean), 6),
        "median": round(median(clean), 6),
        "min": round(min(clean), 6),
        "max": round(max(clean), 6),
        "win_rate": round(len(wins) / len(clean), 4),
    }


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "date": row["Date"],
                "open": clean_float(row.get("Open")),
                "high": clean_float(row.get("High")),
                "low": clean_float(row.get("Low")),
                "close": clean_float(row.get("Close")),
                "volume": clean_float(row.get("Volume")),
            }
        )
    return sorted(normalized, key=lambda item: item["date"])


def row_by_date(rows: list[dict[str, Any]]) -> dict[str, tuple[int, dict[str, Any]]]:
    return {row["date"]: (idx, row) for idx, row in enumerate(rows)}


def forward_return(
    rows: list[dict[str, Any]], entry_idx: int, horizon: int
) -> float | None:
    exit_idx = entry_idx + horizon
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    return pct_change(rows[exit_idx]["close"], rows[entry_idx]["open"])


def collect_backtest_context(result: dict[str, Any]) -> dict[str, Any]:
    entered_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ab_candidate_by_date_ticker: set[tuple[str, str]] = set()

    def visit(window: dict[str, Any]) -> None:
        for trade in window.get("trades") or []:
            day = trade.get("entry_date")
            ticker = trade.get("ticker")
            strategy = trade.get("strategy")
            if not day or strategy not in {"trend_long", "breakout_long"}:
                continue
            entered_by_date[day].append(trade)
            if ticker:
                ab_candidate_by_date_ticker.add((day, ticker))
        ee = window.get("entry_execution_attribution") or {}
        for skip in ee.get("sample_skips") or []:
            day = skip.get("date")
            ticker = skip.get("ticker")
            strategy = skip.get("strategy")
            if not day or strategy not in {"trend_long", "breakout_long"}:
                continue
            skipped_by_date[day].append(skip)
            if ticker:
                ab_candidate_by_date_ticker.add((day, ticker))

    visit(result)
    if isinstance(result.get("primary"), dict):
        visit(result["primary"])
    if isinstance(result.get("secondary"), dict):
        visit(result["secondary"])

    return {
        "entered_by_date": entered_by_date,
        "skipped_by_date": skipped_by_date,
        "ab_candidate_by_date_ticker": ab_candidate_by_date_ticker,
    }


def registry_metadata() -> dict[str, Any]:
    registry = load_json(UNIVERSE_REGISTRY)
    tickers = registry.get("tickers") or {}
    return {
        ticker: {
            key: tickers.get(ticker, {}).get(key)
            for key in [
                "status",
                "theme",
                "discovered_as_of",
                "eligible_as_of",
                "first_trade_allowed_as_of",
                "history_class",
                "liquidity_tier",
                "competes_for_core_slots",
            ]
        }
        for ticker in SHADOW_TICKERS
    }


def scan_window(
    window: dict[str, Any], context: dict[str, Any], registry: dict[str, Any]
) -> dict[str, Any]:
    snapshot = load_json(window["snapshot"])
    ohlcv = {
        ticker: normalize_rows(rows)
        for ticker, rows in (snapshot.get("ohlcv") or {}).items()
    }
    qqq_rows = ohlcv[BENCHMARK]
    qqq_index = row_by_date(qqq_rows)
    qqq_window_dates = [
        row["date"]
        for row in qqq_rows
        if window["start"] <= row["date"] <= window["end"]
    ]
    candidates = []
    coverage = {}

    for ticker in SHADOW_TICKERS:
        rows = ohlcv.get(ticker) or []
        date_index = row_by_date(rows)
        rows_in_window = [
            row for row in rows if window["start"] <= row["date"] <= window["end"]
        ]
        prior_rows = [row for row in rows if row["date"] < window["start"]]
        coverage[ticker] = {
            "rows_in_window": len(rows_in_window),
            "benchmark_rows_in_window": len(qqq_window_dates),
            "coverage_ratio": round(
                len(rows_in_window) / len(qqq_window_dates), 4
            )
            if qqq_window_dates
            else None,
            "prior_rows_available_at_window_start": len(prior_rows),
            "has_min_lookback_at_window_start": len(prior_rows) >= LOOKBACK_DAYS,
        }
        last_signal_idx = -10_000
        for idx, row in enumerate(rows):
            day = row["date"]
            if day < window["start"] or day > window["end"]:
                continue
            if idx < LOOKBACK_DAYS or idx - last_signal_idx <= COOLDOWN_DAYS:
                continue
            if day not in qqq_index:
                continue
            qqq_idx, qqq_row = qqq_index[day]
            if qqq_idx < LOOKBACK_DAYS:
                continue
            history = rows[idx - LOOKBACK_DAYS : idx]
            qqq_history = qqq_rows[qqq_idx - LOOKBACK_DAYS : qqq_idx]
            prev_high = max(item["high"] for item in history if item["high"])
            dollar_volume_20d = mean(
                (item["close"] or 0) * (item["volume"] or 0) for item in history
            )
            ticker_ret20 = pct_change(row["close"], rows[idx - LOOKBACK_DAYS]["close"])
            qqq_ret20 = pct_change(qqq_row["close"], qqq_history[0]["close"])
            rs20 = None
            if ticker_ret20 is not None and qqq_ret20 is not None:
                rs20 = ticker_ret20 - qqq_ret20
            entry_idx = idx + 1
            if (
                row["close"] is None
                or row["close"] < MIN_CLOSE
                or row["close"] <= prev_high
                or dollar_volume_20d < MIN_DOLLAR_VOLUME_20D
                or rs20 is None
                or rs20 < MIN_RS20_VS_QQQ
                or entry_idx >= len(rows)
            ):
                continue
            entry_day = rows[entry_idx]["date"]
            qqq_entry = qqq_index.get(entry_day)
            fwd = {
                f"fwd_{horizon}d_return": forward_return(rows, entry_idx, horizon)
                for horizon in FORWARD_HORIZONS
            }
            if qqq_entry:
                qqq_entry_idx, _ = qqq_entry
                for horizon in FORWARD_HORIZONS:
                    qqq_fwd = forward_return(qqq_rows, qqq_entry_idx, horizon)
                    raw = fwd[f"fwd_{horizon}d_return"]
                    fwd[f"fwd_{horizon}d_excess_vs_qqq"] = (
                        raw - qqq_fwd
                        if raw is not None and qqq_fwd is not None
                        else None
                    )
            same_day_entered = context["entered_by_date"].get(entry_day, [])
            same_day_skipped = context["skipped_by_date"].get(entry_day, [])
            scarce_skips = [
                skip
                for skip in same_day_skipped
                if skip.get("decision") in SCARCE_SLOT_DECISIONS
            ]
            entered_pnls = [
                trade.get("pnl_pct_net")
                for trade in same_day_entered
                if isinstance(trade.get("pnl_pct_net"), (int, float))
            ]
            candidate = {
                "ticker": ticker,
                "signal_date": day,
                "entry_date": entry_day,
                "signal_close": round(row["close"], 4),
                "entry_open": round(rows[entry_idx]["open"], 4)
                if rows[entry_idx]["open"] is not None
                else None,
                "prev_20d_high": round(prev_high, 4),
                "rs20_vs_qqq": round(rs20, 6),
                "ticker_ret20": round(ticker_ret20, 6),
                "qqq_ret20": round(qqq_ret20, 6),
                "dollar_volume_20d": round(dollar_volume_20d, 2),
                "same_ticker_ab_overlap": (entry_day, ticker)
                in context["ab_candidate_by_date_ticker"],
                "same_day_ab_entered_count": len(same_day_entered),
                "same_day_ab_skipped_count": len(same_day_skipped),
                "same_day_scarce_slot_skip_count": len(scarce_skips),
                "scarce_slot_skip_tickers": sorted(
                    {
                        skip.get("ticker")
                        for skip in scarce_skips
                        if skip.get("ticker")
                    }
                ),
                "replacement_proxy_vs_same_day_entered_avg_pnl_pct": (
                    fwd.get("fwd_10d_return") - mean(entered_pnls)
                    if fwd.get("fwd_10d_return") is not None and entered_pnls
                    else None
                ),
                "pit_universe_status": registry.get(ticker, {}).get("status"),
                "registry_discovered_as_of": registry.get(ticker, {}).get(
                    "discovered_as_of"
                ),
                "static_pool_lookback_before_discovery": (
                    registry.get(ticker, {}).get("discovered_as_of") is not None
                    and entry_day < registry[ticker]["discovered_as_of"]
                ),
            }
            candidate.update(
                {
                    key: round(value, 6) if isinstance(value, float) else value
                    for key, value in fwd.items()
                }
            )
            candidates.append(candidate)
            last_signal_idx = idx

    returns_by_horizon = {
        f"fwd_{horizon}d_return": summarize(
            [
                candidate[f"fwd_{horizon}d_return"]
                for candidate in candidates
                if candidate.get(f"fwd_{horizon}d_return") is not None
            ]
        )
        for horizon in FORWARD_HORIZONS
    }
    excess_by_horizon = {
        f"fwd_{horizon}d_excess_vs_qqq": summarize(
            [
                candidate[f"fwd_{horizon}d_excess_vs_qqq"]
                for candidate in candidates
                if candidate.get(f"fwd_{horizon}d_excess_vs_qqq") is not None
            ]
        )
        for horizon in FORWARD_HORIZONS
    }
    dollar_volumes = [candidate["dollar_volume_20d"] for candidate in candidates]
    replacement_values = [
        candidate["replacement_proxy_vs_same_day_entered_avg_pnl_pct"]
        for candidate in candidates
        if candidate.get("replacement_proxy_vs_same_day_entered_avg_pnl_pct")
        is not None
    ]

    return {
        "window": {
            "name": window["name"],
            "start": window["start"],
            "end": window["end"],
            "snapshot": window["snapshot"].relative_to(REPO_ROOT).as_posix(),
        },
        "candidate_count": len(candidates),
        "candidate_count_by_ticker": {
            ticker: sum(1 for candidate in candidates if candidate["ticker"] == ticker)
            for ticker in SHADOW_TICKERS
        },
        "same_ticker_ab_overlap_count": sum(
            1 for candidate in candidates if candidate["same_ticker_ab_overlap"]
        ),
        "same_day_ab_activity_count": sum(
            1
            for candidate in candidates
            if candidate["same_day_ab_entered_count"]
            or candidate["same_day_ab_skipped_count"]
        ),
        "same_day_scarce_slot_overlap_count": sum(
            1
            for candidate in candidates
            if candidate["same_day_scarce_slot_skip_count"]
        ),
        "data_coverage": coverage,
        "liquidity": {
            "min_candidate_dollar_volume_20d": round(min(dollar_volumes), 2)
            if dollar_volumes
            else None,
            "median_candidate_dollar_volume_20d": round(median(dollar_volumes), 2)
            if dollar_volumes
            else None,
            "passes_liquidity_floor_count": sum(
                1 for value in dollar_volumes if value >= MIN_DOLLAR_VOLUME_20D
            ),
        },
        "survivorship_risk": {
            "classification": "high_static_current_pilot_names_applied_backward",
            "candidates_before_registry_discovery": sum(
                1
                for candidate in candidates
                if candidate["static_pool_lookback_before_discovery"]
            ),
            "candidate_count": len(candidates),
            "note": (
                "All candidates are research-only historical shadow observations; "
                "registry discovery dates do not permit production promotion from "
                "this static sample."
            ),
        },
        "forward_return_distribution": returns_by_horizon,
        "forward_excess_distribution_vs_qqq": excess_by_horizon,
        "scarce_slot_replacement_proxy": {
            "candidate_count_with_same_day_scarce_slot_skip": sum(
                1
                for candidate in candidates
                if candidate["same_day_scarce_slot_skip_count"]
            ),
            "replacement_proxy_vs_same_day_entered_avg_pnl_pct": summarize(
                replacement_values
            ),
            "feasibility_note": (
                "Replacement proxy is available only when the baseline result has "
                "same-day entered A/B trades; it is not a full slot-aware replay."
            ),
        },
        "candidates": candidates,
    }


def main() -> None:
    registry = registry_metadata()
    context = collect_backtest_context(load_json(BACKTEST_RESULT))
    windows = [scan_window(window, context, registry) for window in WINDOWS]
    all_candidates = [
        candidate for window in windows for candidate in window["candidates"]
    ]
    aggregate_returns = {
        f"fwd_{horizon}d_return": summarize(
            [
                candidate[f"fwd_{horizon}d_return"]
                for candidate in all_candidates
                if candidate.get(f"fwd_{horizon}d_return") is not None
            ]
        )
        for horizon in FORWARD_HORIZONS
    }
    aggregate_excess = {
        f"fwd_{horizon}d_excess_vs_qqq": summarize(
            [
                candidate[f"fwd_{horizon}d_excess_vs_qqq"]
                for candidate in all_candidates
                if candidate.get(f"fwd_{horizon}d_excess_vs_qqq") is not None
            ]
        )
        for horizon in FORWARD_HORIZONS
    }
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classification": "universe_scout",
        "status_recommendation": "observed_only",
        "production_promotion_justified": False,
        "why_not_promote": [
            "Static current-pilot-name sample is not point-in-time promotion evidence.",
            "Candidate count is expected to be too small for universe promotion.",
            "No slot-aware production replay or live pilot replacement outcomes were produced.",
        ],
        "alpha_hypothesis": {
            "type": "universe_definition",
            "definition": (
                "Current AI-infrastructure pilot names BE/INTC/LITE only; "
                "signal when close breaks the prior 20-trading-day high, 20-day "
                "return exceeds QQQ by at least 5 percentage points, 20-day "
                "average dollar volume is at least $20M, and close is at least $10. "
                "Entry is next open with a 10-trading-day per-ticker cooldown."
            ),
            "category": "universe_scout",
            "why_not_recent_rejected_mechanisms": (
                "This is not broad universe expansion, 10-K same-sample promotion, "
                "or Form 4 cluster promotion; it is a narrow OHLCV-only pilot-name "
                "shadow universe audit."
            ),
        },
        "parameters": {
            "shadow_tickers": SHADOW_TICKERS,
            "benchmark": BENCHMARK,
            "lookback_days": LOOKBACK_DAYS,
            "min_rs20_vs_qqq": MIN_RS20_VS_QQQ,
            "min_dollar_volume_20d": MIN_DOLLAR_VOLUME_20D,
            "min_close": MIN_CLOSE,
            "cooldown_days": COOLDOWN_DAYS,
            "forward_horizons": FORWARD_HORIZONS,
        },
        "registry_metadata": registry,
        "baseline_result_file": BACKTEST_RESULT.relative_to(REPO_ROOT).as_posix(),
        "windows": windows,
        "aggregate": {
            "candidate_count": len(all_candidates),
            "candidate_count_by_ticker": {
                ticker: sum(
                    1 for candidate in all_candidates if candidate["ticker"] == ticker
                )
                for ticker in SHADOW_TICKERS
            },
            "same_ticker_ab_overlap_count": sum(
                1
                for candidate in all_candidates
                if candidate["same_ticker_ab_overlap"]
            ),
            "same_day_ab_activity_count": sum(
                1
                for candidate in all_candidates
                if candidate["same_day_ab_entered_count"]
                or candidate["same_day_ab_skipped_count"]
            ),
            "same_day_scarce_slot_overlap_count": sum(
                1
                for candidate in all_candidates
                if candidate["same_day_scarce_slot_skip_count"]
            ),
            "forward_return_distribution": aggregate_returns,
            "forward_excess_distribution_vs_qqq": aggregate_excess,
        },
    }
    write_json(OUTPUT_PATH, payload)
    print(json.dumps(payload["aggregate"], indent=2, sort_keys=True))
    print(OUTPUT_PATH.relative_to(REPO_ROOT).as_posix())


if __name__ == "__main__":
    main()
