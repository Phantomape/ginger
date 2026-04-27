"""Observed-only hold-quality taxonomy for accepted-stack bad trades.

This audit does not change strategy behavior. It replays the accepted stack on
fixed OHLCV snapshots, classifies each completed trade by post-entry hold
quality, and estimates winner collateral for future lifecycle experiments.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260427-004"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260427_004_hold_quality_taxonomy.json",
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "regime": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "regime": "rotation-heavy bull with weaker follow-through",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "regime": "mixed-to-weak older tape",
    }),
])

CONFIG = {"REGIME_AWARE_EXIT": True}


def _load_snapshot(path: str) -> dict[str, list[dict]]:
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("ohlcv", {})


def _run_window(universe: list[str], cfg: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _trade_rows(snapshot: dict[str, list[dict]], trade: dict) -> list[dict]:
    rows = snapshot.get(trade.get("ticker"), [])
    entry = trade.get("entry_date")
    exit_ = trade.get("exit_date")
    if not entry or not exit_:
        return []
    return [row for row in rows if entry <= row.get("Date", "") <= exit_]


def _safe_return(price: float | None, base: float | None) -> float | None:
    if isinstance(price, (int, float)) and isinstance(base, (int, float)) and base > 0:
        return (price / base) - 1.0
    return None


def _round(value: float | None, ndigits: int = 6) -> float | None:
    return round(value, ndigits) if isinstance(value, (int, float)) else None


def _idx_of_extreme(values: list[float], value: float | None) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    try:
        return values.index(value)
    except ValueError:
        return None


def _quality_label(
    *,
    mfe_pct: float | None,
    mae_pct: float | None,
    target_progress: float | None,
    first_three_close_peak_pct: float | None,
    first_three_close_trough_pct: float | None,
    positive_close_ratio: float | None,
    days_to_mfe: int | None,
    hold_days: int,
) -> str:
    """Path-only family label; PnL is deliberately not an input."""
    if isinstance(target_progress, (int, float)) and target_progress >= 0.5:
        return "good_run_then_giveback_risk"
    if isinstance(mfe_pct, (int, float)) and mfe_pct >= 0.05:
        return "strong_mfe_unfinished"
    if (
        isinstance(mfe_pct, (int, float))
        and mfe_pct >= 0.02
        and isinstance(days_to_mfe, int)
        and days_to_mfe <= 3
        and isinstance(positive_close_ratio, (int, float))
        and positive_close_ratio < 0.5
    ):
        return "early_pop_failed_hold"
    if (
        isinstance(first_three_close_trough_pct, (int, float))
        and first_three_close_trough_pct <= -0.03
        and isinstance(first_three_close_peak_pct, (int, float))
        and first_three_close_peak_pct <= 0.0
    ):
        return "early_flush_no_reclaim"
    if isinstance(mfe_pct, (int, float)) and mfe_pct < 0.01:
        return "low_mfe_no_progress"
    if (
        isinstance(mfe_pct, (int, float))
        and mfe_pct < 0.02
        and hold_days >= 3
        and isinstance(positive_close_ratio, (int, float))
        and positive_close_ratio < 0.5
    ):
        return "stall_below_two_pct"
    if isinstance(mae_pct, (int, float)) and mae_pct <= -0.04:
        return "deep_mae_recovery_attempt"
    if isinstance(positive_close_ratio, (int, float)) and positive_close_ratio >= 0.67:
        return "orderly_positive_hold"
    return "mixed_hold_quality"


def _diagnostics(trade: dict, snapshot: dict[str, list[dict]]) -> dict:
    rows = _trade_rows(snapshot, trade)
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    target_mult = trade.get("target_mult_used")

    highs = [row.get("High") for row in rows if isinstance(row.get("High"), (int, float))]
    lows = [row.get("Low") for row in rows if isinstance(row.get("Low"), (int, float))]
    closes = [row.get("Close") for row in rows if isinstance(row.get("Close"), (int, float))]

    max_high = max(highs) if highs else None
    min_low = min(lows) if lows else None
    mfe_pct = _safe_return(max_high, entry)
    mae_pct = _safe_return(min_low, entry)
    days_to_mfe = _idx_of_extreme(highs, max_high)
    days_to_mae = _idx_of_extreme(lows, min_low)
    hold_days = len(rows)

    positive_close_count = sum(1 for close in closes if isinstance(entry, (int, float)) and close > entry)
    positive_close_ratio = (positive_close_count / len(closes)) if closes else None
    first_three_close_peak_pct = _safe_return(max(closes[:3]), entry) if closes else None
    first_three_close_trough_pct = _safe_return(min(closes[:3]), entry) if closes else None
    final_close_return_pct = _safe_return(closes[-1], entry) if closes else None

    stop_distance_pct = None
    target_progress = None
    if isinstance(entry, (int, float)) and isinstance(stop, (int, float)) and entry > stop:
        stop_distance_pct = (entry - stop) / entry
        if isinstance(target_mult, (int, float)) and target_mult > 0 and isinstance(max_high, (int, float)):
            target_price = entry + ((entry - stop) * target_mult)
            if target_price > entry:
                target_progress = (max_high - entry) / (target_price - entry)

    quality_family = _quality_label(
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        target_progress=target_progress,
        first_three_close_peak_pct=first_three_close_peak_pct,
        first_three_close_trough_pct=first_three_close_trough_pct,
        positive_close_ratio=positive_close_ratio,
        days_to_mfe=days_to_mfe,
        hold_days=hold_days,
    )

    pnl = trade.get("pnl") or 0.0
    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "exit_reason": trade.get("exit_reason"),
        "pnl": _round(pnl, 2),
        "pnl_pct_net": trade.get("pnl_pct_net"),
        "entry_price": entry,
        "exit_price": trade.get("exit_price"),
        "hold_days_observed": hold_days,
        "mfe_pct": _round(mfe_pct),
        "mae_pct": _round(mae_pct),
        "target_progress": _round(target_progress),
        "stop_distance_pct": _round(stop_distance_pct),
        "days_to_mfe": days_to_mfe,
        "days_to_mae": days_to_mae,
        "positive_close_ratio": _round(positive_close_ratio),
        "first_three_close_peak_pct": _round(first_three_close_peak_pct),
        "first_three_close_trough_pct": _round(first_three_close_trough_pct),
        "final_close_return_pct": _round(final_close_return_pct),
        "quality_family": quality_family,
        "is_bad_trade": pnl <= 0,
        "is_good_trade": pnl > 0,
    }


def _summary(rows: list[dict]) -> dict:
    pnls = [row["pnl"] for row in rows if isinstance(row.get("pnl"), (int, float))]
    mfe_values = [row["mfe_pct"] for row in rows if isinstance(row.get("mfe_pct"), (int, float))]
    mae_values = [row["mae_pct"] for row in rows if isinstance(row.get("mae_pct"), (int, float))]
    return {
        "count": len(rows),
        "pnl_sum": round(sum(pnls), 2) if pnls else 0.0,
        "avg_pnl": round(mean(pnls), 2) if pnls else None,
        "median_pnl": round(median(pnls), 2) if pnls else None,
        "winner_count": sum(1 for pnl in pnls if pnl > 0),
        "loser_count": sum(1 for pnl in pnls if pnl <= 0),
        "avg_mfe_pct": _round(mean(mfe_values)) if mfe_values else None,
        "avg_mae_pct": _round(mean(mae_values)) if mae_values else None,
    }


def _counter(rows: list[dict], key: str) -> dict:
    return dict(sorted(Counter(row.get(key) or "unknown" for row in rows).items()))


def _quality_summaries(rows: list[dict]) -> dict:
    by_family = defaultdict(list)
    for row in rows:
        by_family[row["quality_family"]].append(row)
    return {family: _summary(items) for family, items in sorted(by_family.items())}


def _bad_family_rows(rows: list[dict], family: str) -> list[dict]:
    return [
        row for row in rows
        if row["quality_family"] == family and row["is_bad_trade"]
    ]


def _winner_collateral_rows(rows: list[dict], family: str) -> list[dict]:
    return [
        row for row in rows
        if row["quality_family"] == family and row["is_good_trade"]
    ]


def _candidate_assessment(rows: list[dict]) -> list[dict]:
    families = sorted({row["quality_family"] for row in rows if row["is_bad_trade"]})
    candidates = []
    for family in families:
        bad = _bad_family_rows(rows, family)
        good = _winner_collateral_rows(rows, family)
        bad_pnl_abs = abs(sum(row.get("pnl") or 0.0 for row in bad))
        good_pnl = sum(row.get("pnl") or 0.0 for row in good)
        collateral_ratio = (good_pnl / bad_pnl_abs) if bad_pnl_abs > 0 else None
        if not bad:
            risk_level = "none"
        elif not good:
            risk_level = "low_observed_collateral"
        elif collateral_ratio is not None and collateral_ratio <= 0.5:
            risk_level = "moderate_observed_collateral"
        else:
            risk_level = "high_observed_collateral"
        candidates.append({
            "quality_family": family,
            "bad_summary": _summary(bad),
            "winner_collateral_summary": _summary(good),
            "winner_collateral_to_bad_pnl_abs_ratio": _round(collateral_ratio, 4),
            "likely_good_trade_false_positive_risk": risk_level,
            "future_fix_candidate": _future_fix_candidate(family, risk_level),
        })
    return sorted(
        candidates,
        key=lambda row: (
            row["likely_good_trade_false_positive_risk"] == "high_observed_collateral",
            -(row["bad_summary"]["count"]),
            row["bad_summary"]["pnl_sum"],
        ),
    )


def _future_fix_candidate(family: str, risk_level: str) -> str:
    if risk_level == "high_observed_collateral":
        return "Do not convert directly; require an orthogonal discriminator before replay."
    if family == "low_mfe_no_progress":
        return "Potential lifecycle response candidate only after adding non-price adverse information."
    if family == "early_flush_no_reclaim":
        return "Potential narrow lifecycle audit candidate; avoid pre-entry filtering."
    if family == "stall_below_two_pct":
        return "Potential hold-management candidate, but first test persistence and winner collateral by strategy."
    if family == "early_pop_failed_hold":
        return "Potential giveback-management candidate; must avoid truncating strong MFE winners."
    if family == "good_run_then_giveback_risk":
        return "Potential exit-quality candidate, not an entry filter."
    return "Observed family; gather more samples before any strategy replay."


def _window_audit(label: str, cfg: dict, universe: list[str]) -> dict:
    result = _run_window(universe, cfg)
    snapshot = _load_snapshot(os.path.join(REPO_ROOT, cfg["snapshot"]))
    rows = [_diagnostics(trade, snapshot) for trade in result.get("trades", [])]
    bad_rows = [row for row in rows if row["is_bad_trade"]]
    good_rows = [row for row in rows if row["is_good_trade"]]

    return {
        "date_range": {"start": cfg["start"], "end": cfg["end"]},
        "snapshot": cfg["snapshot"],
        "market_regime_summary": cfg["regime"],
        "metrics": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe": result.get("sharpe"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_pnl": result.get("total_pnl"),
            "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
            "survival_rate": result.get("survival_rate"),
        },
        "trade_quality_counts": _counter(rows, "quality_family"),
        "bad_trade_quality_counts": _counter(bad_rows, "quality_family"),
        "good_trade_quality_counts": _counter(good_rows, "quality_family"),
        "bad_by_family": _quality_summaries(bad_rows),
        "good_by_family": _quality_summaries(good_rows),
        "future_fix_candidates": _candidate_assessment(rows),
        "bad_trade_rows": sorted(
            bad_rows,
            key=lambda row: (row["quality_family"], row.get("pnl") or 0.0),
        ),
    }


def _aggregate(windows: OrderedDict[str, dict]) -> dict:
    all_bad_rows = []
    all_good_rows = []
    for label, payload in windows.items():
        for row in payload["bad_trade_rows"]:
            tagged = dict(row)
            tagged["window"] = label
            all_bad_rows.append(tagged)
        # Reconstruct good collateral from compact summaries is impossible, so
        # retain candidate assessments by summing window-level rows below.
    bad_by_family = _quality_summaries(all_bad_rows)
    family_counts_by_window = {
        label: payload["bad_trade_quality_counts"]
        for label, payload in windows.items()
    }
    families_seen_in_multiple_windows = sorted(
        family for family in bad_by_family
        if sum(1 for counts in family_counts_by_window.values() if counts.get(family, 0) > 0) >= 2
    )

    # Use window-level candidate summaries to preserve good-trade collateral
    # without bloating the artifact with all winning trade rows.
    candidate_rollup = defaultdict(lambda: {
        "bad_count": 0,
        "bad_pnl_sum": 0.0,
        "winner_collateral_count": 0,
        "winner_collateral_pnl_sum": 0.0,
        "windows_with_bad": 0,
    })
    for payload in windows.values():
        for candidate in payload["future_fix_candidates"]:
            family = candidate["quality_family"]
            bad = candidate["bad_summary"]
            good = candidate["winner_collateral_summary"]
            candidate_rollup[family]["bad_count"] += bad["count"]
            candidate_rollup[family]["bad_pnl_sum"] += bad["pnl_sum"]
            candidate_rollup[family]["winner_collateral_count"] += good["count"]
            candidate_rollup[family]["winner_collateral_pnl_sum"] += good["pnl_sum"]
            if bad["count"] > 0:
                candidate_rollup[family]["windows_with_bad"] += 1

    candidates = []
    for family, values in sorted(candidate_rollup.items()):
        bad_abs = abs(values["bad_pnl_sum"])
        collateral_ratio = values["winner_collateral_pnl_sum"] / bad_abs if bad_abs > 0 else None
        if values["winner_collateral_count"] == 0:
            risk_level = "low_observed_collateral"
        elif collateral_ratio is not None and collateral_ratio <= 0.5:
            risk_level = "moderate_observed_collateral"
        else:
            risk_level = "high_observed_collateral"
        candidates.append({
            "quality_family": family,
            "bad_count": values["bad_count"],
            "bad_pnl_sum": round(values["bad_pnl_sum"], 2),
            "winner_collateral_count": values["winner_collateral_count"],
            "winner_collateral_pnl_sum": round(values["winner_collateral_pnl_sum"], 2),
            "winner_collateral_to_bad_pnl_abs_ratio": _round(collateral_ratio, 4),
            "windows_with_bad": values["windows_with_bad"],
            "likely_good_trade_false_positive_risk": risk_level,
            "future_fix_candidate": _future_fix_candidate(family, risk_level),
        })

    return {
        "bad_trade_count": len(all_bad_rows),
        "bad_trade_pnl_sum": round(sum(row.get("pnl") or 0.0 for row in all_bad_rows), 2),
        "bad_by_family": bad_by_family,
        "families_seen_in_multiple_windows": families_seen_in_multiple_windows,
        "candidate_rollup": sorted(
            candidates,
            key=lambda row: (
                -row["windows_with_bad"],
                -row["bad_count"],
                row["bad_pnl_sum"],
            ),
        ),
    }


def main() -> int:
    universe = get_universe()
    windows = OrderedDict()
    for label, cfg in WINDOWS.items():
        windows[label] = _window_audit(label, cfg, universe)

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "change_type": "failure_taxonomy",
        "single_causal_variable": "bad trade hold-quality taxonomy",
        "strategy_behavior_changed": False,
        "filters_added": False,
        "config": CONFIG,
        "thresholds": {
            "low_mfe_pct": 0.01,
            "stall_mfe_pct": 0.02,
            "strong_mfe_pct": 0.05,
            "early_flush_close_trough_pct": -0.03,
            "half_target_progress": 0.5,
        },
        "windows": windows,
        "aggregate": _aggregate(windows),
        "notes": [
            "This is observed-only loss attribution; it is not evidence to add a filter.",
            "Winner collateral is measured by matching the same hold-quality label on profitable trades.",
            "Families with high observed collateral require an orthogonal discriminator before any replay.",
        ],
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": os.path.relpath(OUT_JSON, REPO_ROOT),
        "aggregate": payload["aggregate"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
