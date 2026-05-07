"""Observed-only event/state-qualified shadow-universe scout.

This experiment does not change production strategy code. It reuses the frozen
external event-bundle candidate rows and audits whether a single state
qualifier produces a smaller, liquid, low-overlap shadow universe with useful
forward-return and scarce-slot value.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "exp-20260506-026"
ROOT = Path(__file__).resolve().parents[2]
SOURCE_ARTIFACT = ROOT / "data/experiments/exp-20260505-026/exp_20260505_026_event_bundle_universe_scout.json"
OUTPUT = ROOT / "data/experiments/exp-20260506-026/exp_20260506_026_event_state_qualified_shadow_universe.json"

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": ROOT / "data/ohlcv_snapshot_20251023_20260421.json",
        "baseline": ROOT / "data/experiments/exp-20260505-025/baseline_late_strong.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": ROOT / "data/ohlcv_snapshot_20250423_20251022.json",
        "baseline": ROOT / "data/experiments/exp-20260505-025/baseline_mid_weak.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": ROOT / "data/ohlcv_snapshot_20241002_20250422.json",
        "baseline": ROOT / "data/experiments/exp-20260505-025/baseline_old_thin.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    },
}

MIN_DOLLAR_VOLUME = 20_000_000
ROUND_TRIP_COST = 0.0035


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def date_index(rows: list[dict]) -> dict[str, int]:
    return {row["Date"]: i for i, row in enumerate(rows)}


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct(value: float | None) -> float | None:
    return round(value * 100, 4) if value is not None else None


def distribution(values: list[float]) -> dict:
    values = [v for v in values if v is not None]
    if not values:
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
    ordered = sorted(values)
    return {
        "count": len(values),
        "avg_pct": pct(mean(values)),
        "median_pct": pct(statistics.median(values)),
        "p25_pct": pct(ordered[int((len(ordered) - 1) * 0.25)]),
        "p75_pct": pct(ordered[int((len(ordered) - 1) * 0.75)]),
        "win_rate": round(sum(1 for v in values if v > 0) / len(values), 4),
        "best_pct": pct(max(values)),
        "worst_pct": pct(min(values)),
    }


def forward_return(rows: list[dict], idx: int, horizon: int) -> tuple[float | None, str | None]:
    if idx < 0 or idx + horizon >= len(rows):
        return None, None
    entry = rows[idx]["Close"]
    exit_row = rows[idx + horizon]
    if not entry:
        return None, None
    return (exit_row["Close"] / entry) - 1.0, exit_row["Date"]


def trailing_state(rows: list[dict], spy_rows: list[dict], idx: int, spy_idx: int) -> dict:
    if idx < 50 or spy_idx < 20:
        return {
            "state_covered": False,
            "state_pass": False,
            "reason": "insufficient_lookback",
        }
    close = rows[idx]["Close"]
    close_20 = rows[idx - 20]["Close"]
    spy_close = spy_rows[spy_idx]["Close"]
    spy_close_20 = spy_rows[spy_idx - 20]["Close"]
    ma50 = mean([r["Close"] for r in rows[idx - 49 : idx + 1]])
    dollar_vol_20 = mean([r["Close"] * r["Volume"] for r in rows[idx - 19 : idx + 1]])
    ticker_20d_return = (close / close_20) - 1.0
    spy_20d_return = (spy_close / spy_close_20) - 1.0
    excess_20d = ticker_20d_return - spy_20d_return
    state_pass = bool(
        dollar_vol_20 is not None
        and dollar_vol_20 >= MIN_DOLLAR_VOLUME
        and ma50 is not None
        and close >= ma50
        and excess_20d > 0
    )
    return {
        "state_covered": True,
        "state_pass": state_pass,
        "close_above_50d": bool(ma50 is not None and close >= ma50),
        "ticker_20d_return": round(ticker_20d_return, 6),
        "spy_20d_return": round(spy_20d_return, 6),
        "excess_20d_return": round(excess_20d, 6),
        "median_20d_dollar_volume": round(dollar_vol_20, 2) if dollar_vol_20 is not None else None,
        "liquidity_pass": bool(dollar_vol_20 is not None and dollar_vol_20 >= MIN_DOLLAR_VOLUME),
        "reason": "pass" if state_pass else "state_or_liquidity_fail",
    }


def baseline_trade_sets(path: Path) -> dict:
    data = load_json(path)
    trades = data.get("trades", [])
    same_day = {(t.get("entry_date"), t.get("ticker")) for t in trades}
    date_to_pnls: dict[str, list[float]] = {}
    for t in trades:
        date_to_pnls.setdefault(t.get("entry_date"), []).append(float(t.get("pnl") or 0.0))
    skipped = data.get("entry_execution_attribution", {}).get("sample_skips", [])
    deferred = data.get("scarce_slot_attribution", {}).get("deferred_events", [])
    candidate_like = set(same_day)
    for row in skipped:
        candidate_like.add((row.get("date"), row.get("ticker")))
    for row in deferred:
        candidate_like.add((row.get("date"), row.get("ticker")))
    return {
        "metrics": {
            "expected_value_score": data.get("expected_value_score"),
            "sharpe_daily": data.get("sharpe_daily"),
            "total_pnl": data.get("total_pnl"),
            "max_drawdown_pct": data.get("max_drawdown_pct"),
            "win_rate": data.get("win_rate"),
            "trade_count": data.get("total_trades"),
            "survival_rate": data.get("survival_rate"),
        },
        "same_day_trade_keys": same_day,
        "candidate_like_keys": candidate_like,
        "date_to_pnls": date_to_pnls,
        "trades": trades,
    }


def load_snapshot(path: Path) -> dict[str, list[dict]]:
    data = load_json(path)
    return data["ohlcv"]


def candidate_rows(source: dict) -> list[dict]:
    rows = []
    for window, payload in source["windows"].items():
        for row in payload.get("candidate_rows", []):
            item = dict(row)
            item["window"] = window
            rows.append(item)
    return rows


def analyze() -> dict:
    source = load_json(SOURCE_ARTIFACT)
    rows = candidate_rows(source)
    by_window = {name: [] for name in WINDOWS}
    rejected_by_state = {name: [] for name in WINDOWS}
    data_missing = {name: [] for name in WINDOWS}

    for name, cfg in WINDOWS.items():
        snap = load_snapshot(cfg["snapshot"])
        spy = snap.get("SPY")
        if not spy:
            raise RuntimeError(f"SPY missing from {cfg['snapshot']}")
        spy_idx = date_index(spy)
        baseline = baseline_trade_sets(cfg["baseline"])
        for row in [r for r in rows if r["window"] == name]:
            ticker = row["ticker"]
            entry_date = row.get("entry_date_used") or row.get("entry_date")
            ticker_rows = snap.get(ticker)
            if not ticker_rows:
                missed = dict(row)
                missed["coverage_reason"] = "ticker_missing_from_snapshot"
                data_missing[name].append(missed)
                continue
            idx_map = date_index(ticker_rows)
            if entry_date not in idx_map or entry_date not in spy_idx:
                missed = dict(row)
                missed["coverage_reason"] = "entry_date_missing_from_snapshot"
                data_missing[name].append(missed)
                continue
            idx = idx_map[entry_date]
            sidx = spy_idx[entry_date]
            state = trailing_state(ticker_rows, spy, idx, sidx)
            enriched = dict(row)
            enriched.update(state)
            for horizon in (5, 10, 20):
                ret, exit_date = forward_return(ticker_rows, idx, horizon)
                spy_ret, _ = forward_return(spy, sidx, horizon)
                enriched[f"forward_{horizon}d_return"] = round(ret, 6) if ret is not None else None
                enriched[f"forward_{horizon}d_excess_return"] = (
                    round(ret - spy_ret, 6) if ret is not None and spy_ret is not None else None
                )
                enriched[f"forward_{horizon}d_exit_date"] = exit_date
            trade_key = (entry_date, ticker)
            same_day_pnls = baseline["date_to_pnls"].get(entry_date, [])
            same_day_avg = mean(same_day_pnls)
            notional_pnl_10d = None
            if enriched["forward_10d_return"] is not None:
                notional_pnl_10d = 10_000 * (enriched["forward_10d_return"] - ROUND_TRIP_COST)
            enriched.update(
                {
                    "same_ticker_same_day_ab_or_c_trade_overlap": trade_key in baseline["same_day_trade_keys"],
                    "same_ticker_same_day_ab_or_c_candidate_overlap": trade_key in baseline["candidate_like_keys"],
                    "same_day_core_trade_count": len(same_day_pnls),
                    "same_day_core_avg_pnl": round(same_day_avg, 2) if same_day_avg is not None else None,
                    "shadow_10k_10d_net_pnl": round(notional_pnl_10d, 2) if notional_pnl_10d is not None else None,
                    "scarce_slot_value_vs_same_day_core_avg_pnl": (
                        round(notional_pnl_10d - same_day_avg, 2)
                        if notional_pnl_10d is not None and same_day_avg is not None
                        else None
                    ),
                }
            )
            if state["state_pass"]:
                by_window[name].append(enriched)
            else:
                rejected_by_state[name].append(enriched)

    window_reports = {}
    selected_all = []
    for name, selected in by_window.items():
        cfg = WINDOWS[name]
        baseline = baseline_trade_sets(cfg["baseline"])
        selected_all.extend(selected)
        fwd = {}
        for horizon in (5, 10, 20):
            fwd[f"{horizon}d"] = {
                "return": distribution([r[f"forward_{horizon}d_return"] for r in selected]),
                "excess_return": distribution([r[f"forward_{horizon}d_excess_return"] for r in selected]),
            }
        scarce_values = [
            r["scarce_slot_value_vs_same_day_core_avg_pnl"]
            for r in selected
            if r["scarce_slot_value_vs_same_day_core_avg_pnl"] is not None
        ]
        window_reports[name] = {
            "window": {"start": cfg["start"], "end": cfg["end"], "state_note": cfg["state_note"]},
            "baseline_metrics": baseline["metrics"],
            "candidate_count_source": len([r for r in rows if r["window"] == name]),
            "candidate_count_selected": len(selected),
            "candidate_count_state_rejected": len(rejected_by_state[name]),
            "data_missing_count": len(data_missing[name]),
            "unique_selected_tickers": sorted({r["ticker"] for r in selected}),
            "data_coverage_rate": round(
                (len(selected) + len(rejected_by_state[name]))
                / max(1, len(selected) + len(rejected_by_state[name]) + len(data_missing[name])),
                4,
            ),
            "liquidity_pass_rate_selected": round(
                sum(1 for r in selected if r["liquidity_pass"]) / max(1, len(selected)),
                4,
            ),
            "same_ticker_same_day_trade_overlap_rate": round(
                sum(1 for r in selected if r["same_ticker_same_day_ab_or_c_trade_overlap"]) / max(1, len(selected)),
                4,
            ),
            "same_ticker_same_day_candidate_overlap_rate": round(
                sum(1 for r in selected if r["same_ticker_same_day_ab_or_c_candidate_overlap"]) / max(1, len(selected)),
                4,
            ),
            "forward_return_distribution": fwd,
            "scarce_slot_value": {
                "same_day_comparable_count": len(scarce_values),
                "distribution_vs_same_day_core_avg_pnl": distribution([v / 10_000 for v in scarce_values]),
                "avg_shadow_10k_10d_net_pnl": round(
                    mean([r["shadow_10k_10d_net_pnl"] for r in selected if r["shadow_10k_10d_net_pnl"] is not None]) or 0.0,
                    2,
                ),
            },
            "selected_rows": selected,
            "state_rejected_sample": rejected_by_state[name][:10],
            "data_missing_sample": data_missing[name][:10],
        }

    aggregate = {
        "source_candidate_count": len(rows),
        "selected_candidate_count": len(selected_all),
        "unique_selected_ticker_count": len({r["ticker"] for r in selected_all}),
        "unique_selected_tickers": sorted({r["ticker"] for r in selected_all}),
        "windows_with_positive_median_10d_excess": sum(
            1
            for report in window_reports.values()
            if (report["forward_return_distribution"]["10d"]["excess_return"]["median_pct"] or 0) > 0
        ),
        "windows_with_positive_avg_10d_excess": sum(
            1
            for report in window_reports.values()
            if (report["forward_return_distribution"]["10d"]["excess_return"]["avg_pct"] or 0) > 0
        ),
        "windows_with_low_trade_overlap": sum(
            1 for report in window_reports.values() if report["same_ticker_same_day_trade_overlap_rate"] <= 0.10
        ),
        "windows_with_coverage_ge_90pct": sum(
            1 for report in window_reports.values() if report["data_coverage_rate"] >= 0.90
        ),
        "windows_with_liquidity_pass_100pct": sum(
            1 for report in window_reports.values() if report["liquidity_pass_rate_selected"] == 1.0
        ),
    }
    promotion_grade = bool(
        aggregate["selected_candidate_count"] >= 20
        and aggregate["windows_with_positive_median_10d_excess"] == 3
        and aggregate["windows_with_low_trade_overlap"] == 3
        and aggregate["windows_with_coverage_ge_90pct"] == 3
        and aggregate["windows_with_liquidity_pass_100pct"] == 3
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "observed_only",
        "decision": "observed_only" if not promotion_grade else "shadow_promising_not_promoted",
        "hypothesis": "A narrow event/state-qualified shadow universe can surface non-overlapping candidates with better scarce-slot value than broad watchlist expansion.",
        "single_causal_variable": "event-state-qualified shadow universe",
        "change_type": "universe_expansion",
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
        "history_guardrail": {
            "not_repeating": [
                "broad historical-attention-list universe expansion rejected in exp-20260505-009",
                "consumer digital platform sub-basket simple gates rejected in exp-20260505-020",
                "crypto-beta guarded pool rejected in exp-20260506-012",
                "same-sample event-bundle source-composition retuning rejected in exp-20260505-004",
            ],
            "why_this_is_not_duplicate": "This is a shadow-only audit of a frozen event source plus one price/state qualifier. It does not add broad tickers, retune event thresholds, or modify production strategy code.",
        },
        "parameters": {
            "source_artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)),
            "event_source": "frozen default-off external event bundle candidate rows",
            "state_qualifier": {
                "min_median_20d_dollar_volume": MIN_DOLLAR_VOLUME,
                "close_above_50d": True,
                "ticker_20d_excess_return_vs_spy": "> 0",
            },
            "forward_horizons": [5, 10, 20],
            "shadow_notional_for_slot_value": 10_000,
            "round_trip_cost": ROUND_TRIP_COST,
        },
        "aggregate": aggregate,
        "promotion_grade_evidence": promotion_grade,
        "decision_rationale": (
            "Observed-only: the scout is non-production and promotion would require robust multi-window "
            "replacement value plus default-off forward paper outcomes. This artifact is sufficient for "
            "continued observation only unless the window metrics are promotion-grade."
        ),
        "windows": window_reports,
    }


def main() -> None:
    result = analyze()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "output": str(OUTPUT.relative_to(ROOT)),
        "decision": result["decision"],
        "aggregate": result["aggregate"],
    }, indent=2))


if __name__ == "__main__":
    main()
