"""exp-20260426-035 post-earnings continuation shadow audit.

This is not a production strategy and does not touch `earnings_event_long`.
It tests one replayable mechanism: after an earnings event day
(`days_to_earnings == 0`), require the ticker to confirm with a +2% next-day
close-to-close move and positive relative strength versus SPY.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
MIN_NEXT_DAY_RETURN = 0.02
MIN_RS_VS_SPY = 0.0
FORWARD_DAYS = (5, 10, 20)

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_035_post_earnings_continuation_shadow.json",
)


def _load_snapshot(path: str) -> dict:
    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("ohlcv", raw)


def _series(snapshot: dict, ticker: str) -> list[dict]:
    rows = snapshot.get(ticker) or []
    return sorted(rows, key=lambda row: str(row.get("Date") or row.get("date")))


def _date(row: dict) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def _close(row: dict) -> float | None:
    value = row.get("Close")
    return float(value) if isinstance(value, (int, float)) else None


def _row_index(rows: list[dict]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows)}


def _load_earnings_snapshot(date_key: str) -> dict:
    path = os.path.join(REPO_ROOT, "data", f"earnings_snapshot_{date_key}.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("earnings", {})


def _run_baseline(universe: list[str], cfg: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def _forward_return(rows: list[dict], start_idx: int, horizon: int) -> float | None:
    end_idx = start_idx + horizon
    if end_idx >= len(rows):
        return None
    start_close = _close(rows[start_idx])
    end_close = _close(rows[end_idx])
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _summarize(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
        }
    return {
        "count": len(values),
        "avg": round(mean(values), 6),
        "median": round(median(values), 6),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def _audit_window(universe: list[str], cfg: dict) -> dict:
    snapshot = _load_snapshot(cfg["snapshot"])
    spy_rows = _series(snapshot, "SPY")
    spy_index = _row_index(spy_rows)
    baseline = _run_baseline(universe, cfg)
    baseline_entries = defaultdict(list)
    for trade in baseline.get("trades", []):
        strategy = trade.get("strategy")
        if strategy in {"trend_long", "breakout_long"}:
            baseline_entries[str(trade.get("entry_date"))[:10]].append(trade)

    candidates = []
    event_days_seen = 0
    raw_event_count = 0
    skipped_no_confirm_day = 0
    skipped_failed_confirmation = 0
    for date, spy_idx in spy_index.items():
        if date < cfg["start"] or date > cfg["end"]:
            continue
        earnings = _load_earnings_snapshot(date.replace("-", ""))
        if not earnings:
            continue
        event_days_seen += 1
        for ticker, event in earnings.items():
            if ticker not in snapshot:
                continue
            if event.get("days_to_earnings") != 0:
                continue
            raw_event_count += 1
            rows = _series(snapshot, ticker)
            idx_by_date = _row_index(rows)
            event_idx = idx_by_date.get(date)
            if event_idx is None or event_idx + 1 >= len(rows):
                skipped_no_confirm_day += 1
                continue
            confirm_idx = event_idx + 1
            confirm_date = _date(rows[confirm_idx])
            if confirm_date > cfg["end"]:
                continue
            event_close = _close(rows[event_idx])
            confirm_close = _close(rows[confirm_idx])
            if not event_close or confirm_close is None:
                continue
            ticker_ret = (confirm_close / event_close) - 1.0
            if spy_idx + 1 >= len(spy_rows):
                continue
            spy_event_close = _close(spy_rows[spy_idx])
            spy_confirm_close = _close(spy_rows[spy_idx + 1])
            if not spy_event_close or spy_confirm_close is None:
                continue
            spy_ret = (spy_confirm_close / spy_event_close) - 1.0
            rs_vs_spy = ticker_ret - spy_ret
            if ticker_ret < MIN_NEXT_DAY_RETURN or rs_vs_spy <= MIN_RS_VS_SPY:
                skipped_failed_confirmation += 1
                continue

            forwards = {
                f"fwd_{horizon}d": _forward_return(rows, confirm_idx, horizon)
                for horizon in FORWARD_DAYS
            }
            same_day_entries = baseline_entries.get(confirm_date, [])
            same_ticker_overlap = any(trade.get("ticker") == ticker for trade in same_day_entries)
            candidates.append({
                "ticker": ticker,
                "event_date": date,
                "candidate_date": confirm_date,
                "ticker_next_day_return": round(ticker_ret, 6),
                "spy_next_day_return": round(spy_ret, 6),
                "rs_vs_spy": round(rs_vs_spy, 6),
                "avg_historical_surprise_pct": event.get("avg_historical_surprise_pct"),
                "eps_estimate": event.get("eps_estimate"),
                "eps_actual_last": event.get("eps_actual_last"),
                "same_day_ab_entry_count": len(same_day_entries),
                "same_day_ab_overlap": bool(same_day_entries),
                "same_ticker_ab_overlap": same_ticker_overlap,
                **{
                    key: round(value, 6) if isinstance(value, float) else None
                    for key, value in forwards.items()
                },
            })

    forward_summary = {}
    for horizon in FORWARD_DAYS:
        key = f"fwd_{horizon}d"
        forward_summary[key] = _summarize([
            candidate[key] for candidate in candidates
            if isinstance(candidate.get(key), (int, float))
        ])

    same_day_overlap = sum(1 for candidate in candidates if candidate["same_day_ab_overlap"])
    same_ticker_overlap = sum(1 for candidate in candidates if candidate["same_ticker_ab_overlap"])
    candidate_days = sorted({candidate["candidate_date"] for candidate in candidates})
    scarce_slot_proxy = {
        "candidate_days": len(candidate_days),
        "candidate_days_with_ab_entries": len({
            candidate["candidate_date"] for candidate in candidates
            if candidate["same_day_ab_overlap"]
        }),
        "avg_ab_entries_on_candidate_day": (
            round(mean([candidate["same_day_ab_entry_count"] for candidate in candidates]), 4)
            if candidates else None
        ),
        "max_ab_entries_on_candidate_day": (
            max(candidate["same_day_ab_entry_count"] for candidate in candidates)
            if candidates else None
        ),
    }
    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "baseline_metrics": _metrics(baseline),
        "event_days_with_earnings_snapshot": event_days_seen,
        "raw_dte0_event_count": raw_event_count,
        "skipped_no_confirm_day": skipped_no_confirm_day,
        "skipped_failed_confirmation": skipped_failed_confirmation,
        "candidate_count": len(candidates),
        "same_day_ab_overlap_count": same_day_overlap,
        "same_day_ab_overlap_rate": round(same_day_overlap / len(candidates), 4) if candidates else None,
        "same_ticker_ab_overlap_count": same_ticker_overlap,
        "same_ticker_ab_overlap_rate": round(same_ticker_overlap / len(candidates), 4) if candidates else None,
        "scarce_slot_proxy": scarce_slot_proxy,
        "forward_return_summary": forward_summary,
        "candidates": candidates,
    }


def main() -> int:
    universe = get_universe()
    results = {
        "experiment_id": "exp-20260426-037",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "hypothesis": (
            "A post-earnings price-confirmed continuation shadow strategy may "
            "identify replayable PEAD-style candidates with better non-overlap "
            "and forward-return quality than rejected scalar/checklist C revival."
        ),
        "single_causal_variable": "post_earnings_price_confirmed_continuation_shadow_entry",
        "parameters": {
            "event_condition": "earnings_snapshot.days_to_earnings == 0",
            "confirmation": {
                "next_trading_day_ticker_close_to_close_min": MIN_NEXT_DAY_RETURN,
                "next_trading_day_rs_vs_spy_min": MIN_RS_VS_SPY,
            },
            "forward_return_horizons": list(FORWARD_DAYS),
        },
        "windows": {},
    }
    for label, cfg in WINDOWS.items():
        results["windows"][label] = _audit_window(universe, cfg)

    all_10d = []
    total_candidates = 0
    overlap_count = 0
    for rec in results["windows"].values():
        total_candidates += rec["candidate_count"]
        overlap_count += rec["same_day_ab_overlap_count"]
        all_10d.extend([
            candidate["fwd_10d"] for candidate in rec["candidates"]
            if isinstance(candidate.get("fwd_10d"), (int, float))
        ])
    results["aggregate_summary"] = {
        "candidate_count": total_candidates,
        "same_day_ab_overlap_count": overlap_count,
        "same_day_ab_overlap_rate": (
            round(overlap_count / total_candidates, 4) if total_candidates else None
        ),
        "fwd_10d": _summarize(all_10d),
    }
    results["decision"] = "observed_only"
    results["production_promotion"] = False
    results["production_promotion_reason"] = (
        "Shadow-only audit. Requires a real strategy replay and slot model before "
        "any production consideration."
    )

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "aggregate_summary": results["aggregate_summary"],
        "window_candidate_counts": {
            label: rec["candidate_count"] for label, rec in results["windows"].items()
        },
        "decision": results["decision"],
    }, indent=2))
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
