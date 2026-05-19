"""exp-20260507-005: state-aware shadow alpha surface.

Observed-only alpha discovery. This runner reads the latest meta-allocation
state map and canonical OHLCV snapshots, then builds a shadow-only candidate
surface from state-conditioned continuous scores. It does not alter production
strategy code, entry ordering, sizing, exits, universe membership, LLM, or news.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


EXPERIMENT_ID = "exp-20260507-005"
STEM = "state_aware_shadow_alpha_surface"

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260507_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
META_MAP_JSON = REPO_ROOT / "data" / "experiments" / "exp-20260506-024" / "meta_allocation_state_map.json"
RESULT_FILES = {
    "late_strong": REPO_ROOT / "data" / "backtest_results_20260506.json",
    "mid_weak": REPO_ROOT / "data" / "backtest_results_20260506.json",
    "old_thin": REPO_ROOT / "data" / "backtest_results_20260504.json",
}
RESULT_KEYS = {
    "late_strong": "primary",
    "mid_weak": "secondary",
    "old_thin": "primary",
}
INDEX_TICKERS = {"SPY", "QQQ", "IWM"}


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
        "converged": bool((result.get("convergence") or {}).get("converged")),
    }


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected snapshot shape: {snapshot_path}")
    return {
        str(ticker).upper(): sorted(rows, key=lambda row: row.get("Date", ""))
        for ticker, rows in ohlcv.items()
        if isinstance(rows, list)
    }


def _close(row: dict[str, Any]) -> float | None:
    try:
        value = float(row.get("Close"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _volume(row: dict[str, Any]) -> float | None:
    try:
        value = float(row.get("Volume"))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _rows_until(rows: list[dict[str, Any]], date_str: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row.get("Date") or "") <= date_str]


def _ret(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) <= lookback:
        return None
    now = _close(hist[-1])
    then = _close(hist[-lookback - 1])
    if not now or not then:
        return None
    return now / then - 1.0


def _future_ret(rows: list[dict[str, Any]], date_str: str, horizon: int) -> float | None:
    dates = [str(row.get("Date") or "") for row in rows]
    try:
        idx = dates.index(date_str)
    except ValueError:
        return None
    if idx + horizon >= len(rows):
        return None
    now = _close(rows[idx])
    future = _close(rows[idx + horizon])
    if not now or not future:
        return None
    return future / now - 1.0


def _pct_from_sma(rows: list[dict[str, Any]], date_str: str, lookback: int) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback:
        return None
    now = _close(hist[-1])
    closes = [_close(row) for row in hist[-lookback:]]
    closes = [value for value in closes if value]
    if not now or len(closes) < lookback:
        return None
    avg = sum(closes) / len(closes)
    return now / avg - 1.0 if avg else None


def _volume_ratio(rows: list[dict[str, Any]], date_str: str, lookback: int = 20) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback + 1:
        return None
    now = _volume(hist[-1])
    vols = [_volume(row) for row in hist[-lookback - 1 : -1]]
    vols = [value for value in vols if value]
    if not now or len(vols) < lookback:
        return None
    avg = sum(vols) / len(vols)
    return now / avg if avg else None


def _near_high(rows: list[dict[str, Any]], date_str: str, lookback: int = 60) -> float | None:
    hist = _rows_until(rows, date_str)
    if len(hist) < lookback:
        return None
    now = _close(hist[-1])
    highs = []
    for row in hist[-lookback:]:
        try:
            highs.append(float(row.get("High")))
        except (TypeError, ValueError):
            continue
    if not now or not highs:
        return None
    high = max(highs)
    return now / high if high else None


def _breadth(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
    lookback: int,
) -> float | None:
    seen = 0
    above = 0
    for ticker in universe:
        rows = ohlcv.get(ticker.upper())
        if not rows:
            continue
        pct = _pct_from_sma(rows, date_str, lookback)
        if pct is None:
            continue
        seen += 1
        above += int(pct > 0)
    return above / seen if seen else None


def _sector_dispersion(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> float | None:
    by_sector: dict[str, list[float]] = defaultdict(list)
    for ticker in universe:
        rows = ohlcv.get(ticker.upper())
        if not rows:
            continue
        value = _ret(rows, date_str, 20)
        if value is None:
            continue
        by_sector["all_snapshot_tickers"].append(value)
    sector_returns = [
        sum(values) / len(values) for values in by_sector.values() if values
    ]
    if len(sector_returns) < 2:
        return None
    return statistics.pstdev(sector_returns)


def _state_for_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
) -> dict[str, Any]:
    spy_rows = ohlcv.get("SPY", [])
    qqq_rows = ohlcv.get("QQQ", [])
    iwm_rows = ohlcv.get("IWM", [])
    spy_ret20 = _ret(spy_rows, date_str, 20)
    qqq_ret20 = _ret(qqq_rows, date_str, 20)
    iwm_ret20 = _ret(iwm_rows, date_str, 20)
    spy_pct200 = _pct_from_sma(spy_rows, date_str, 200)
    qqq_pct200 = _pct_from_sma(qqq_rows, date_str, 200)
    breadth50 = _breadth(ohlcv, universe, date_str, 50)
    dispersion20 = _sector_dispersion(ohlcv, universe, date_str)

    pct_values = [value for value in (spy_pct200, qqq_pct200) if value is not None]
    min_index_pct200 = min(pct_values) if pct_values else None
    qqq_minus_iwm = None
    if qqq_ret20 is not None and iwm_ret20 is not None:
        qqq_minus_iwm = qqq_ret20 - iwm_ret20
    iwm_minus_spy = None
    if iwm_ret20 is not None and spy_ret20 is not None:
        iwm_minus_spy = iwm_ret20 - spy_ret20

    if min_index_pct200 is not None and min_index_pct200 < 0:
        state_bucket = "weak_index"
    elif qqq_minus_iwm is not None and qqq_minus_iwm > 0.04:
        state_bucket = "narrow_cap_weight_leadership"
    elif iwm_minus_spy is not None and iwm_minus_spy > 0.02:
        state_bucket = "broad_rotation"
    else:
        state_bucket = "balanced_risk_on"

    if breadth50 is None:
        breadth_bucket = "unknown"
    elif breadth50 >= 0.65:
        breadth_bucket = "broad_breadth"
    elif breadth50 <= 0.45:
        breadth_bucket = "thin_breadth"
    else:
        breadth_bucket = "mixed_breadth"

    if dispersion20 is None:
        dispersion_bucket = "unknown"
    elif dispersion20 >= 0.08:
        dispersion_bucket = "high_sector_dispersion"
    elif dispersion20 <= 0.035:
        dispersion_bucket = "low_sector_dispersion"
    else:
        dispersion_bucket = "mid_sector_dispersion"

    return {
        "state_bucket": state_bucket,
        "breadth_bucket": breadth_bucket,
        "dispersion_bucket": dispersion_bucket,
        "spy_ret20": _round(spy_ret20, 6),
        "qqq_ret20": _round(qqq_ret20, 6),
        "iwm_ret20": _round(iwm_ret20, 6),
        "qqq_minus_iwm_ret20": _round(qqq_minus_iwm, 6),
        "iwm_minus_spy_ret20": _round(iwm_minus_spy, 6),
        "min_index_pct_from_200sma": _round(min_index_pct200, 6),
        "universe_breadth_above_50sma": _round(breadth50, 6),
        "sector_ret20_dispersion": _round(dispersion20, 6),
    }


def _load_result(label: str) -> dict[str, Any]:
    payload = json.loads(RESULT_FILES[label].read_text(encoding="utf-8", errors="replace"))
    key = RESULT_KEYS[label]
    result = payload.get(key) if isinstance(payload.get(key), dict) else payload
    if not isinstance(result, dict):
        raise RuntimeError(f"Missing result block {key} in {RESULT_FILES[label]}")
    return result


def _ab_events(result: dict[str, Any]) -> dict[str, Any]:
    entered = {
        (str(trade.get("entry_date")), str(trade.get("ticker")).upper())
        for trade in result.get("trades", [])
        if trade.get("entry_date") and trade.get("ticker")
    }
    all_candidates = set(entered)
    skips = (result.get("entry_execution_attribution") or {}).get("sample_skips") or []
    pressure_dates = set()
    by_date = (result.get("entry_execution_attribution") or {}).get("by_date") or {}
    for date_str, counts in by_date.items():
        if (counts or {}).get("slot_sliced", 0) or (counts or {}).get("no_shares", 0):
            pressure_dates.add(str(date_str))
    for skip in skips:
        date_str = str(skip.get("date") or "")
        ticker = str(skip.get("ticker") or "").upper()
        if date_str and ticker:
            all_candidates.add((date_str, ticker))
            if skip.get("decision") in {"slot_sliced", "no_shares"}:
                pressure_dates.add(date_str)
    return {
        "entered": entered,
        "all_candidates": all_candidates,
        "pressure_dates": pressure_dates,
        "entered_by_date": defaultdict(list),
    }


def _build_entered_by_date(
    result: dict[str, Any],
    ohlcv: dict[str, list[dict[str, Any]]],
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for trade in result.get("trades", []):
        date_str = str(trade.get("entry_date") or "")
        ticker = str(trade.get("ticker") or "").upper()
        rows = ohlcv.get(ticker)
        if not date_str or not rows:
            continue
        fwd20 = _future_ret(rows, date_str, 20)
        if fwd20 is not None:
            out[date_str].append(fwd20)
    return out


def _zscore_map(values: dict[str, float]) -> dict[str, float]:
    clean = [value for value in values.values() if value is not None]
    if len(clean) < 2:
        return {key: 0.0 for key in values}
    mean = statistics.mean(clean)
    stdev = statistics.pstdev(clean) or 1.0
    return {key: (value - mean) / stdev for key, value in values.items()}


def _score_candidates_for_date(
    ohlcv: dict[str, list[dict[str, Any]]],
    universe: list[str],
    date_str: str,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    features: dict[str, dict[str, float]] = {}
    for ticker in universe:
        rows = ohlcv.get(ticker.upper())
        if not rows:
            continue
        if date_str not in {str(row.get("Date") or "") for row in rows}:
            continue
        ret20 = _ret(rows, date_str, 20)
        ret60 = _ret(rows, date_str, 60)
        ret5 = _ret(rows, date_str, 5)
        near_high = _near_high(rows, date_str, 60)
        vol_ratio = _volume_ratio(rows, date_str, 20)
        spy_ret20 = float(state.get("spy_ret20") or 0.0)
        if None in (ret20, ret60, ret5, near_high, vol_ratio):
            continue
        features[ticker.upper()] = {
            "ret20_excess_spy": float(ret20) - spy_ret20,
            "ret60": float(ret60),
            "ret5": float(ret5),
            "near_high_60": float(near_high),
            "volume_ratio_20": float(vol_ratio),
        }
    if not features:
        return []

    z_ret20 = _zscore_map({t: f["ret20_excess_spy"] for t, f in features.items()})
    z_ret60 = _zscore_map({t: f["ret60"] for t, f in features.items()})
    z_pause = _zscore_map({t: -abs(f["ret5"]) for t, f in features.items()})
    z_high = _zscore_map({t: f["near_high_60"] for t, f in features.items()})
    z_volume = _zscore_map({t: f["volume_ratio_20"] for t, f in features.items()})

    state_bucket = str(state.get("state_bucket") or "")
    breadth_bucket = str(state.get("breadth_bucket") or "")
    dispersion_bucket = str(state.get("dispersion_bucket") or "")
    candidates = []
    for ticker, values in features.items():
        if state_bucket == "broad_rotation":
            surface = "rotation_breakout_leadership"
            score = 0.45 * z_ret20[ticker] + 0.25 * z_high[ticker] + 0.20 * z_volume[ticker] + 0.10 * z_ret60[ticker]
        elif breadth_bucket == "broad_breadth":
            surface = "broad_breadth_trend_persistence"
            score = 0.40 * z_ret60[ticker] + 0.25 * z_ret20[ticker] + 0.20 * z_pause[ticker] + 0.15 * z_high[ticker]
        elif dispersion_bucket == "mid_sector_dispersion":
            surface = "mid_dispersion_selective_leadership"
            score = 0.35 * z_ret20[ticker] + 0.30 * z_ret60[ticker] + 0.20 * z_high[ticker] + 0.15 * z_volume[ticker]
        else:
            surface = "balanced_state_leadership"
            score = 0.35 * z_ret60[ticker] + 0.35 * z_ret20[ticker] + 0.20 * z_high[ticker] + 0.10 * z_pause[ticker]
        candidates.append(
            {
                "date": date_str,
                "ticker": ticker,
                "surface": surface,
                "score": _round(score, 6),
                "sector": "snapshot_universe",
                "state_bucket": state_bucket,
                "breadth_bucket": breadth_bucket,
                "dispersion_bucket": dispersion_bucket,
                "features": {key: _round(value, 6) for key, value in values.items()},
            }
        )
    return sorted(candidates, key=lambda row: (row["score"], row["ticker"]), reverse=True)


def _summarize_returns(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return {"count": 0, "avg": None, "median": None, "hit_rate": None, "p25": None, "p75": None}
    values = sorted(float(value) for value in values)
    return {
        "count": len(values),
        "avg": _round(sum(values) / len(values), 6),
        "median": _round(statistics.median(values), 6),
        "hit_rate": _round(sum(1 for value in values if value > 0) / len(values), 4),
        "p25": _round(values[int((len(values) - 1) * 0.25)], 6),
        "p75": _round(values[int((len(values) - 1) * 0.75)], 6),
    }


def _analyze_window(label: str, window: dict[str, str]) -> dict[str, Any]:
    result = _load_result(label)
    ohlcv = _load_ohlcv(REPO_ROOT / window["snapshot"])
    universe = sorted(ticker for ticker in ohlcv if ticker.upper() not in INDEX_TICKERS)
    ab = _ab_events(result)
    entered_by_date = _build_entered_by_date(result, ohlcv)

    spy_dates = [
        str(row.get("Date") or "")
        for row in ohlcv.get("SPY", [])
        if window["start"] <= str(row.get("Date") or "") <= window["end"]
    ]
    all_shadow: list[dict[str, Any]] = []
    for date_str in spy_dates:
        state = _state_for_date(ohlcv, universe, date_str)
        day_ranked = _score_candidates_for_date(ohlcv, universe, date_str, state)[:3]
        for rank, candidate in enumerate(day_ranked, start=1):
            ticker = candidate["ticker"]
            rows = ohlcv.get(ticker, [])
            key = (date_str, ticker)
            same_day_entered = entered_by_date.get(date_str, [])
            fwd20 = _future_ret(rows, date_str, 20)
            replacement_value = None
            if same_day_entered and fwd20 is not None:
                replacement_value = fwd20 - statistics.mean(same_day_entered)
            candidate.update(
                {
                    "rank": rank,
                    "overlap_ab_entered": key in ab["entered"],
                    "overlap_ab_candidate": key in ab["all_candidates"],
                    "scarce_slot_pressure_date": date_str in ab["pressure_dates"],
                    "forward_5d": _round(_future_ret(rows, date_str, 5), 6),
                    "forward_10d": _round(_future_ret(rows, date_str, 10), 6),
                    "forward_20d": _round(fwd20, 6),
                    "scarce_slot_replacement_value_20d": _round(replacement_value, 6),
                }
            )
            all_shadow.append(candidate)

    non_overlap = [row for row in all_shadow if not row["overlap_ab_candidate"]]
    pressure = [row for row in non_overlap if row["scarce_slot_pressure_date"]]
    by_surface = {}
    for surface in sorted({row["surface"] for row in all_shadow}):
        surface_rows = [row for row in non_overlap if row["surface"] == surface]
        by_surface[surface] = {
            "candidate_count": len(surface_rows),
            "forward_20d": _summarize_returns(surface_rows, "forward_20d"),
            "scarce_slot_rows": sum(1 for row in surface_rows if row["scarce_slot_pressure_date"]),
            "scarce_slot_replacement_value_20d": _summarize_returns(
                [row for row in surface_rows if row["scarce_slot_replacement_value_20d"] is not None],
                "scarce_slot_replacement_value_20d",
            ),
        }

    return {
        "window": window,
        "baseline_metrics": _metrics(result),
        "candidate_count": len(all_shadow),
        "unique_tickers": len({row["ticker"] for row in all_shadow}),
        "overlap": {
            "ab_entered_overlap_count": sum(1 for row in all_shadow if row["overlap_ab_entered"]),
            "ab_candidate_overlap_count": sum(1 for row in all_shadow if row["overlap_ab_candidate"]),
            "ab_candidate_overlap_rate": _round(
                sum(1 for row in all_shadow if row["overlap_ab_candidate"]) / len(all_shadow)
                if all_shadow
                else 0.0,
                6,
            ),
            "non_overlap_count": len(non_overlap),
        },
        "forward_returns": {
            "all_shadow_20d": _summarize_returns(all_shadow, "forward_20d"),
            "non_overlap_5d": _summarize_returns(non_overlap, "forward_5d"),
            "non_overlap_10d": _summarize_returns(non_overlap, "forward_10d"),
            "non_overlap_20d": _summarize_returns(non_overlap, "forward_20d"),
        },
        "scarce_slot_value": {
            "pressure_date_non_overlap_count": len(pressure),
            "replacement_value_20d": _summarize_returns(
                [row for row in pressure if row["scarce_slot_replacement_value_20d"] is not None],
                "scarce_slot_replacement_value_20d",
            ),
        },
        "by_surface": by_surface,
        "sample_candidates": non_overlap[:25],
        "state_bucket_counts": dict(Counter(row["state_bucket"] for row in all_shadow)),
        "surface_counts": dict(Counter(row["surface"] for row in all_shadow)),
    }


def _aggregate(by_window: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = sum(row["candidate_count"] for row in by_window.values())
    non_overlap = sum(row["overlap"]["non_overlap_count"] for row in by_window.values())
    overlap = sum(row["overlap"]["ab_candidate_overlap_count"] for row in by_window.values())

    def _weighted_summary(path: tuple[str, ...]) -> dict[str, Any]:
        count = 0
        avg_sum = 0.0
        hit_sum = 0.0
        for row in by_window.values():
            summary: Any = row
            for key in path:
                summary = summary.get(key, {}) if isinstance(summary, dict) else {}
            n = int(summary.get("count") or 0)
            if not n or summary.get("avg") is None:
                continue
            count += n
            avg_sum += float(summary.get("avg")) * n
            hit_sum += float(summary.get("hit_rate") or 0.0) * n
        return {
            "count": count,
            "avg": _round(avg_sum / count if count else None, 6),
            "hit_rate": _round(hit_sum / count if count else None, 4),
            "note": "Weighted from per-window summaries; see by_window for medians and quartiles.",
        }

    return {
        "candidate_count": candidates,
        "non_overlap_count": non_overlap,
        "ab_candidate_overlap_count": overlap,
        "ab_candidate_overlap_rate": _round(overlap / candidates if candidates else 0.0, 6),
        "non_overlap_forward_20d": _weighted_summary(
            ("forward_returns", "non_overlap_20d")
        ),
        "pressure_replacement_value_20d": _weighted_summary(
            ("scarce_slot_value", "replacement_value_20d")
        ),
    }


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    meta_map = json.loads(META_MAP_JSON.read_text(encoding="utf-8")) if META_MAP_JSON.exists() else None
    by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, window in WINDOWS.items():
        by_window[label] = _analyze_window(label, window)

    aggregate = _aggregate(by_window)
    decision = "observed_only"
    candidate_useful = (
        aggregate["non_overlap_count"] > 0
        and (aggregate["non_overlap_forward_20d"].get("avg") or 0) > 0
    )
    if candidate_useful:
        alpha_read = "follow_up_candidate_only"
        interpretation = (
            "The shadow surface finds non-overlapping candidates with positive sampled "
            "forward returns, but it is not promotion evidence because no executable "
            "entry, sizing, or slot policy was replayed."
        )
    else:
        alpha_read = "not_useful_as_measured"
        interpretation = (
            "The shadow surface is measurable but does not yet show a useful non-overlap "
            "forward-return profile. Treat it as a logged negative or weak lead."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": generated_at,
        "status": decision,
        "decision": decision,
        "lane": "alpha_discovery",
        "change_type": "new_strategy_shadow",
        "mechanism_family": "state_aware_shadow_alpha_surface",
        "hypothesis": (
            "A state-aware shadow alpha surface from the latest meta-allocation map can "
            "identify non-overlapping candidates without repeating rejected local thresholds."
        ),
        "alpha_hypothesis": {
            "category": "entry / allocation research",
            "why_this_now": (
                "Recent local SPY/Financials retunes, broad universe growth, short-pressure, "
                "options, event-ladder, zero-share, sector-cap, and sixth-slot variants were "
                "rejected. This uses the latest meta-allocation state map only as a shadow "
                "surface and measures overlap, forward returns, and scarce-slot value."
            ),
        },
        "historical_experiment_check": {
            "source_meta_map": str(META_MAP_JSON.relative_to(REPO_ROOT)) if META_MAP_JSON.exists() else None,
            "top_meta_positive_cohorts": (
                (meta_map or {}).get("cohort_findings", {}).get("top_positive_cohorts", [])[:5]
            ),
            "mechanism_no_go_check": (
                "Does not change production strategy code, does not add a universe, does not "
                "use short-pressure/options overlays, does not retune SPY/Financials caps or "
                "targets, and does not change sector caps or zero-share planning."
            ),
        },
        "parameters": {
            "single_causal_variable": "state-aware shadow alpha surface",
            "candidate_selection": "top 3 scored production-universe tickers per trading day",
            "score_design": "continuous state-conditioned cross-sectional score; no production threshold or filter",
            "locked_variables": [
                "production universe",
                "signal generation",
                "entry filters",
                "candidate ranking",
                "risk sizing",
                "position slots",
                "add-ons",
                "exits",
                "LLM/news",
            ],
        },
        "date_range": {label: f"{w['start']} -> {w['end']}" for label, w in WINDOWS.items()},
        "market_regime_summary": {label: w["state_note"] for label, w in WINDOWS.items()},
        "before_metrics": {label: row["baseline_metrics"] for label, row in by_window.items()},
        "after_metrics": {label: row["baseline_metrics"] for label, row in by_window.items()},
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "production_metrics_changed": False,
            "reason": "Shadow measurement only; no executable policy changed.",
        },
        "shadow_metrics": {
            "aggregate": aggregate,
            "by_window": by_window,
        },
        "alpha_read": alpha_read,
        "interpretation": interpretation,
        "acceptance_rule_result": (
            "Observed-only closeout. Promotion is not claimed; a valid follow-up would need "
            "a shared-policy replay proving scarce-slot replacement value across windows."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "orders_changed": False,
        },
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    OUT_JSON.write_text(text + "\n", encoding="utf-8")
    LOG_JSON.write_text(text + "\n", encoding="utf-8")

    existing_ticket: dict[str, Any] = {}
    if TICKET_JSON.exists():
        try:
            existing_ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            existing_ticket = {}
    ticket = {
        **existing_ticket,
        "experiment_id": EXPERIMENT_ID,
        "status": decision,
        "lane": "alpha_discovery",
        "owner": "alpha-discovery",
        "hypothesis": payload["hypothesis"],
        "change_type": "new_strategy_shadow",
        "single_causal_variable": "state-aware shadow alpha surface",
        "baseline_result_file": "data/backtest_results_20260506.json",
        "allowed_write_scope": [
            "quant/experiments/exp_20260507_005_state_aware_shadow_alpha_surface.py",
            "data/experiments/exp-20260507-005/exp_20260507_005_state_aware_shadow_alpha_surface.json",
            "experiments/tickets/exp-20260507-005.json",
            "experiments/logs/exp-20260507-005.json",
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "must_not_touch": [
            "quant/constants.py",
            "quant/signal_engine.py",
            "quant/risk_engine.py",
            "quant/portfolio_engine.py",
            "run.py",
        ],
        "locked_variables": ["state-aware shadow alpha surface"],
        "evaluation_windows": [
            {"start": "2025-10-23", "end": "2026-04-21"},
            {"start": "2025-04-23", "end": "2025-10-22"},
            {"start": "2024-10-02", "end": "2025-04-22"},
        ],
        "acceptance_rule": (
            "shadow mode only; must measure candidates, overlap, forward returns, "
            "and scarce-slot value before any promotion"
        ),
        "generated_at": generated_at,
        "decision": decision,
        "title": "State-aware shadow alpha surface",
        "summary": f"{alpha_read}; {aggregate['non_overlap_count']} non-overlap candidates measured.",
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
        "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
        "shadow_metrics": {
            "candidate_count": aggregate["candidate_count"],
            "non_overlap_count": aggregate["non_overlap_count"],
            "ab_candidate_overlap_rate": aggregate["ab_candidate_overlap_rate"],
            "non_overlap_forward_20d_avg": aggregate["non_overlap_forward_20d"].get("avg"),
            "pressure_replacement_value_20d_avg": aggregate[
                "pressure_replacement_value_20d"
            ].get("avg"),
        },
        "production_impact": payload["production_impact"],
        "completed_at": generated_at,
        "result": {
            "decision": decision,
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
            "log_file": str(LOG_JSON.relative_to(REPO_ROOT)),
            "summary": f"{alpha_read}; shadow-only measurement, no production change.",
        },
    }
    TICKET_JSON.write_text(
        json.dumps(ticket, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"{EXPERIMENT_ID} {decision} {alpha_read}")
    print(json.dumps(ticket["shadow_metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
