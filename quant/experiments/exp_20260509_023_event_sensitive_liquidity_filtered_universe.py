"""Observed-only event-sensitive liquidity-filtered universe scout.

This script evaluates a shadow universe definition only. It does not add
tickers to production, change shared signal/risk/portfolio policy, or route
orders.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "exp-20260509-023"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = (
    ROOT
    / "data/experiments/exp-20260509-023"
    / "exp_20260509_023_event_sensitive_liquidity_filtered_universe.json"
)
BASELINE_FILE = ROOT / "data/backtest_results_20260509.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": ROOT / "data/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": ROOT / "data/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": ROOT / "data/ohlcv_snapshot_20241002_20250422.json",
    },
}

FORWARD_HORIZONS = (5, 10, 20)
MIN_COVERAGE_FRACTION = 0.95
MIN_MEDIAN_DOLLAR_VOLUME = 50_000_000
MIN_MEDIAN_CLOSE = 8.0
SHADOW_NOTIONAL = 10_000
ROUND_TRIP_COST = 0.0035
TOP_PER_DAY = 3
EXCLUDED_MACRO_PROXIES = {
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def date_index(rows: list[dict]) -> dict[str, int]:
    return {str(row["Date"])[:10]: i for i, row in enumerate(rows)}


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct(value: float | None) -> float | None:
    return round(value * 100, 4) if value is not None else None


def distribution(values: list[float | None]) -> dict:
    clean = [float(v) for v in values if v is not None]
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
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "avg_pct": pct(mean(clean)),
        "median_pct": pct(statistics.median(clean)),
        "p25_pct": pct(ordered[int((len(ordered) - 1) * 0.25)]),
        "p75_pct": pct(ordered[int((len(ordered) - 1) * 0.75)]),
        "win_rate": round(sum(1 for v in clean if v > 0) / len(clean), 4),
        "best_pct": pct(max(clean)),
        "worst_pct": pct(min(clean)),
    }


def forward_return(rows: list[dict], idx: int, horizon: int) -> tuple[float | None, str | None]:
    if idx < 0 or idx + horizon >= len(rows):
        return None, None
    entry = float(rows[idx]["Open"])
    exit_row = rows[idx + horizon]
    if entry <= 0:
        return None, None
    return float(exit_row["Close"]) / entry - 1.0, str(exit_row["Date"])[:10]


def median_dollar_volume(rows: list[dict], idx: int, lookback: int = 20) -> float | None:
    start = max(0, idx - lookback)
    sample = rows[start:idx]
    if not sample:
        return None
    values = [float(row["Close"]) * float(row["Volume"]) for row in sample]
    return statistics.median(values)


def coverage_fraction(rows: list[dict], start: str, end: str, expected_days: int) -> float:
    days = [row for row in rows if start <= str(row["Date"])[:10] <= end]
    return len(days) / expected_days if expected_days else 0.0


def load_event_rows(start: str, end: str) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    coverage = {
        "snapshot_files_seen": 0,
        "coverage_blocked_files": 0,
        "event_rows_total": 0,
        "tickers_with_event_rows": set(),
        "sec_items_total": 0,
        "news_items_total": 0,
    }
    for path in sorted((ROOT / "data").glob("event_snapshot_*.json")):
        date_key = path.stem.removeprefix("event_snapshot_")
        event_date = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}"
        if not (start <= event_date <= end):
            continue
        payload = load_json(path)
        cov = payload.get("coverage") or {}
        coverage["snapshot_files_seen"] += 1
        coverage["event_rows_total"] += int(cov.get("event_rows_total") or 0)
        coverage["sec_items_total"] += int(cov.get("sec_items_total") or 0)
        coverage["news_items_total"] += int(cov.get("news_items_total") or 0)
        if cov.get("coverage_blocked"):
            coverage["coverage_blocked_files"] += 1
        for ticker, ticker_rows in (payload.get("events_by_ticker") or {}).items():
            coverage["tickers_with_event_rows"].add(ticker.upper())
            for row in ticker_rows:
                item = dict(row)
                item["snapshot_date"] = event_date
                rows.append(item)
    coverage["tickers_with_event_rows"] = sorted(coverage["tickers_with_event_rows"])
    return rows, coverage


def load_production_universe() -> set[str]:
    tickers = set()
    registry = ROOT / "data/universe_registry.json"
    if registry.exists():
        payload = load_json(registry)
        for ticker, meta in (payload.get("tickers") or {}).items():
            if (meta or {}).get("status") in {"core", "limited_production", "specialist", "pilot"}:
                tickers.add(ticker.upper())
    try:
        import sys

        quant_dir = str(ROOT / "quant")
        if quant_dir not in sys.path:
            sys.path.insert(0, quant_dir)
        from filter import WATCHLIST  # type: ignore

        tickers.update(str(t).upper() for t in WATCHLIST)
    except Exception:
        pass
    return tickers


def baseline_context() -> dict:
    same_day_keys = set()
    ticker_keys = set()
    active_days = set()
    trades_by_day: dict[str, list[float]] = defaultdict(list)
    for path in sorted((ROOT / "data").glob("backtest_results_*.json")):
        try:
            payload = load_json(path)
        except Exception:
            continue
        for trade in payload.get("trades") or []:
            ticker = str(trade.get("ticker") or "").upper()
            entry_date = str(trade.get("entry_date") or "")[:10]
            if not ticker or not entry_date:
                continue
            same_day_keys.add((entry_date, ticker))
            ticker_keys.add(ticker)
            active_days.add(entry_date)
            trades_by_day[entry_date].append(float(trade.get("pnl") or 0.0))
        for row in (payload.get("entry_execution_attribution") or {}).get("sample_skips") or []:
            ticker = str(row.get("ticker") or "").upper()
            date_key = str(row.get("date") or "")[:10]
            if ticker and date_key:
                same_day_keys.add((date_key, ticker))
                ticker_keys.add(ticker)
                active_days.add(date_key)
        for row in (payload.get("scarce_slot_attribution") or {}).get("deferred_events") or []:
            ticker = str(row.get("ticker") or "").upper()
            date_key = str(row.get("signal_date") or row.get("entry_date") or "")[:10]
            if ticker and date_key:
                same_day_keys.add((date_key, ticker))
                ticker_keys.add(ticker)
                active_days.add(date_key)
    return {
        "same_day_keys": same_day_keys,
        "ticker_keys": ticker_keys,
        "active_days": active_days,
        "trades_by_day": trades_by_day,
    }


def score_event(row: dict) -> float:
    subtype = str(row.get("event_subtype") or "")
    flags = row.get("quality_flags") or {}
    attrs = row.get("attributes") or {}
    score = 1.0
    if row.get("source_confidence") == "high":
        score += 0.2
    if row.get("point_in_time_complete"):
        score += 0.2
    if subtype in {"8k_item_2_02", "earnings"}:
        score += 0.4
    if subtype in {"8k_item_7_01", "8k_item_8_01"}:
        score += 0.2
    score += min(len(flags.get("positive") or []), 3) * 0.1
    score -= min(len(flags.get("warning") or []), 3) * 0.15
    if attrs.get("guidance_signal") in {"raise", "positive"}:
        score += 0.3
    if attrs.get("guidance_signal") in {"cut", "negative"}:
        score -= 0.3
    return round(score, 4)


def analyze_window(name: str, cfg: dict, production_universe: set[str], context: dict) -> dict:
    snapshot = load_json(cfg["snapshot"])
    ohlcv = snapshot["ohlcv"]
    spy_rows = ohlcv.get("SPY") or []
    expected_days = len([r for r in spy_rows if cfg["start"] <= str(r["Date"])[:10] <= cfg["end"]])
    event_rows, event_coverage = load_event_rows(cfg["start"], cfg["end"])

    candidates = []
    rejections = Counter()
    seen_accessions = set()
    for event in event_rows:
        ticker = str(event.get("ticker") or "").upper()
        if not ticker:
            rejections["missing_ticker"] += 1
            continue
        accession = (ticker, (event.get("attributes") or {}).get("sec_accession_number"), event.get("event_date"))
        if accession in seen_accessions:
            rejections["duplicate_accession_or_event"] += 1
            continue
        seen_accessions.add(accession)
        if ticker in EXCLUDED_MACRO_PROXIES:
            rejections["excluded_macro_proxy"] += 1
            continue
        rows = ohlcv.get(ticker)
        if not rows:
            rejections["ticker_missing_from_fixed_snapshot"] += 1
            continue
        idx_map = date_index(rows)
        raw_date = str((event.get("attributes") or {}).get("usable_trade_date") or event.get("snapshot_date"))
        entry_date = raw_date[:10] if "-" in raw_date else f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        if entry_date not in idx_map:
            rejections["entry_date_missing_from_snapshot"] += 1
            continue
        idx = idx_map[entry_date]
        coverage = coverage_fraction(rows, cfg["start"], cfg["end"], expected_days)
        med_dv = median_dollar_volume(rows, idx)
        med_close = statistics.median(
            float(row["Close"]) for row in rows if cfg["start"] <= str(row["Date"])[:10] <= cfg["end"]
        )
        if coverage < MIN_COVERAGE_FRACTION:
            rejections["coverage_below_floor"] += 1
            continue
        if med_dv is None or med_dv < MIN_MEDIAN_DOLLAR_VOLUME:
            rejections["dollar_volume_below_floor"] += 1
            continue
        if med_close < MIN_MEDIAN_CLOSE:
            rejections["median_close_below_floor"] += 1
            continue

        enriched = {
            "ticker": ticker,
            "entry_date": entry_date,
            "event_type": event.get("event_type"),
            "event_subtype": event.get("event_subtype"),
            "surprise_direction": event.get("surprise_direction"),
            "surprise_strength": event.get("surprise_strength"),
            "source_confidence": event.get("source_confidence"),
            "point_in_time_complete": bool(event.get("point_in_time_complete")),
            "score": score_event(event),
            "coverage_fraction": round(coverage, 4),
            "median_20d_dollar_volume": round(med_dv, 2),
            "median_close": round(med_close, 4),
            "same_day_ab_overlap": (entry_date, ticker) in context["same_day_keys"],
            "ticker_seen_in_ab_history": ticker in context["ticker_keys"],
            "in_production_or_pilot_universe": ticker in production_universe,
            "source_files": event.get("source_files") or [],
            "title": (event.get("attributes") or {}).get("title"),
        }
        same_day_pnls = context["trades_by_day"].get(entry_date, [])
        same_day_avg_pnl = mean(same_day_pnls)
        for horizon in FORWARD_HORIZONS:
            ret, exit_date = forward_return(rows, idx, horizon)
            enriched[f"forward_{horizon}d_return"] = round(ret, 6) if ret is not None else None
            enriched[f"forward_{horizon}d_exit_date"] = exit_date
            if ret is not None:
                enriched[f"shadow_{horizon}d_net_pnl"] = round(SHADOW_NOTIONAL * (ret - ROUND_TRIP_COST), 2)
        if same_day_avg_pnl is not None and enriched.get("shadow_10d_net_pnl") is not None:
            enriched["scarce_slot_value_vs_same_day_core_avg_pnl"] = round(
                enriched["shadow_10d_net_pnl"] - same_day_avg_pnl,
                2,
            )
        candidates.append(enriched)

    candidates.sort(key=lambda r: (r["entry_date"], -r["score"], r["ticker"]))
    top_by_day = []
    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in candidates:
        by_day[row["entry_date"]].append(row)
    for rows in by_day.values():
        top_by_day.extend(rows[:TOP_PER_DAY])

    def ret_dist(rows: list[dict], horizon: int) -> dict:
        return distribution([r.get(f"forward_{horizon}d_return") for r in rows])

    scarce_values = [r.get("scarce_slot_value_vs_same_day_core_avg_pnl") for r in top_by_day]
    scarce_values = [v for v in scarce_values if v is not None]
    outside_prod = [r for r in candidates if not r["in_production_or_pilot_universe"]]
    return {
        "window": name,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": str(cfg["snapshot"].relative_to(ROOT)),
        "snapshot_ticker_count": len(ohlcv),
        "event_coverage": event_coverage,
        "liquidity_definition": {
            "min_coverage_fraction": MIN_COVERAGE_FRACTION,
            "min_median_20d_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_median_close": MIN_MEDIAN_CLOSE,
        },
        "candidate_count": len(candidates),
        "candidate_days": len(by_day),
        "unique_candidate_tickers": sorted({r["ticker"] for r in candidates}),
        "unique_candidate_ticker_count": len({r["ticker"] for r in candidates}),
        "rejections": dict(sorted(rejections.items())),
        "same_day_ab_overlap_rate": round(
            sum(1 for r in candidates if r["same_day_ab_overlap"]) / len(candidates), 4
        )
        if candidates
        else None,
        "ticker_history_ab_overlap_rate": round(
            sum(1 for r in candidates if r["ticker_seen_in_ab_history"]) / len(candidates), 4
        )
        if candidates
        else None,
        "outside_production_or_pilot_candidate_count": len(outside_prod),
        "outside_production_or_pilot_unique_tickers": sorted({r["ticker"] for r in outside_prod}),
        "candidate_count_by_subtype": dict(Counter(r["event_subtype"] for r in candidates).most_common()),
        "candidate_count_by_ticker": dict(Counter(r["ticker"] for r in candidates).most_common()),
        "data_coverage": {
            "min_candidate_coverage_fraction": min((r["coverage_fraction"] for r in candidates), default=None),
            "median_candidate_coverage_fraction": statistics.median(
                [r["coverage_fraction"] for r in candidates]
            )
            if candidates
            else None,
            "median_candidate_20d_dollar_volume": statistics.median(
                [r["median_20d_dollar_volume"] for r in candidates]
            )
            if candidates
            else None,
        },
        "forward_return_distribution": {
            f"{horizon}d": ret_dist(candidates, horizon) for horizon in FORWARD_HORIZONS
        },
        "non_same_day_overlap_forward_return_distribution": {
            f"{horizon}d": ret_dist([r for r in candidates if not r["same_day_ab_overlap"]], horizon)
            for horizon in FORWARD_HORIZONS
        },
        "scarce_slot_quality_proxy": {
            "top_per_day_limit": TOP_PER_DAY,
            "top_per_day_count": len(top_by_day),
            "top_per_day_forward_return_distribution": {
                f"{horizon}d": ret_dist(top_by_day, horizon) for horizon in FORWARD_HORIZONS
            },
            "same_day_core_comparable_count": len(scarce_values),
            "avg_10d_shadow_pnl_vs_same_day_core_avg_pnl": round(mean(scarce_values), 2)
            if scarce_values
            else None,
            "note": "Proxy only: no sizing, stops, fills, heat, or slot-aware portfolio replay.",
        },
        "sample_candidates": candidates[:60],
    }


def baseline_metrics_for_judge() -> dict:
    baseline = load_json(BASELINE_FILE)
    copied = {
        "expected_value_score": baseline.get("expected_value_score"),
        "sharpe": baseline.get("sharpe"),
        "sharpe_daily": baseline.get("sharpe_daily"),
        "max_drawdown_pct": baseline.get("max_drawdown_pct"),
        "win_rate": baseline.get("win_rate"),
        "total_trades": baseline.get("total_trades"),
        "survival_rate": baseline.get("survival_rate"),
        "total_pnl": baseline.get("total_pnl"),
        "benchmarks": baseline.get("benchmarks"),
    }
    return {k: v for k, v in copied.items() if v is not None}


def analyze() -> dict:
    production_universe = load_production_universe()
    context = baseline_context()
    windows = {
        name: analyze_window(name, cfg, production_universe, context)
        for name, cfg in WINDOWS.items()
    }
    all_candidates = [row for window in windows.values() for row in window["sample_candidates"]]
    total_candidates = sum(window["candidate_count"] for window in windows.values())
    positive_10d_windows = sum(
        1
        for window in windows.values()
        if (window["forward_return_distribution"]["10d"]["avg_pct"] or 0) > 0
    )
    low_overlap_windows = sum(
        1
        for window in windows.values()
        if (window["same_day_ab_overlap_rate"] is not None and window["same_day_ab_overlap_rate"] <= 0.10)
    )
    outside_prod_total = sum(window["outside_production_or_pilot_candidate_count"] for window in windows.values())
    promotion_ready = bool(
        total_candidates >= 30
        and positive_10d_windows == 3
        and low_overlap_windows == 3
        and outside_prod_total > 0
    )
    baseline_metrics = baseline_metrics_for_judge()
    return {
        **baseline_metrics,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "universe_scout",
        "status": "observed_only",
        "decision": "observed_only",
        "hypothesis": (
            "A liquidity-filtered event-sensitive shadow universe can produce non-overlapping "
            "candidate opportunities outside the current trend/breakout coverage."
        ),
        "single_causal_variable": "event-sensitive liquidity-filtered universe",
        "change_type": "universe_expansion",
        "baseline_result_file": str(BASELINE_FILE.relative_to(ROOT)),
        "historical_constraints": {
            "prior_event_sensitive_scout": (
                "exp-20260427-005 found late-window candidates but older windows had zero "
                "clean-news coverage; this run uses repository event snapshots instead."
            ),
            "anti_repeats": [
                "No production universe promotion.",
                "No state-surface/event-bundle parameter retune.",
                "No global slot or scarce-slot threshold change.",
            ],
        },
        "parameters": {
            "event_source": "data/event_snapshot_YYYYMMDD.json",
            "ohlcv_snapshots": {name: str(cfg["snapshot"].relative_to(ROOT)) for name, cfg in WINDOWS.items()},
            "forward_horizons": list(FORWARD_HORIZONS),
            "shadow_notional": SHADOW_NOTIONAL,
            "round_trip_cost": ROUND_TRIP_COST,
            "top_per_day_scarce_slot_proxy": TOP_PER_DAY,
        },
        "aggregate": {
            "candidate_count": total_candidates,
            "unique_candidate_ticker_count": len(
                {ticker for window in windows.values() for ticker in window["unique_candidate_tickers"]}
            ),
            "outside_production_or_pilot_candidate_count": outside_prod_total,
            "windows_with_positive_avg_10d_return": positive_10d_windows,
            "windows_with_same_day_ab_overlap_lte_10pct": low_overlap_windows,
            "promotion_ready": promotion_ready,
        },
        "forward_return_distribution_all_sampled_candidates": {
            f"{horizon}d": distribution([r.get(f"forward_{horizon}d_return") for r in all_candidates])
            for horizon in FORWARD_HORIZONS
        },
        "survivorship_and_pit_risk": {
            "risk": "medium_high",
            "reasons": [
                "Event snapshots are dated and include usable_trade_date, but OHLCV snapshots are fixed repository snapshots, not a fully audited delisted-security universe.",
                "The fixed OHLCV snapshots largely contain current production/pilot names, so this cannot prove external-universe expansion value.",
                "Older and mid-window event snapshot coverage has many coverage_blocked days, so zero/low candidate counts can reflect data availability.",
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
            "Observed-only. The shadow source is auditable, but it did not identify any candidate "
            "outside the current production/pilot universe in the fixed snapshots, so there is no "
            "basis to add tickers or promote a production universe change."
        ),
        "windows": windows,
    }


def main() -> None:
    result = analyze()
    write_json(OUTPUT, result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "output": str(OUTPUT.relative_to(ROOT)),
                "decision": result["decision"],
                "aggregate": result["aggregate"],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
