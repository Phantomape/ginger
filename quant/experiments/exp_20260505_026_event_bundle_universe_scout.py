"""exp-20260505-026 event-bundle universe scout.

Observed-only universe_scout artifact. This does not add tickers to the
production universe and does not change signal, risk, sizing, or portfolio code.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ID = "exp-20260505-026"
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260505_026_event_bundle_universe_scout.json"
)

BUNDLE_JSON = REPO_ROOT / "data" / "experiments" / "exp-20260504-049" / "default_off_event_overlay_bundle.json"
BASELINE_FILES = {
    "late_strong": REPO_ROOT / "data" / "experiments" / "exp-20260505-025" / "baseline_late_strong.json",
    "mid_weak": REPO_ROOT / "data" / "experiments" / "exp-20260505-025" / "baseline_mid_weak.json",
    "old_thin": REPO_ROOT / "data" / "experiments" / "exp-20260505-025" / "baseline_old_thin.json",
}
SNAPSHOT_FILES = OrderedDict(
    [
        ("late_strong", REPO_ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json"),
        ("mid_weak", REPO_ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json"),
        ("old_thin", REPO_ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json"),
    ]
)
WINDOWS = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22"}),
    ]
)
HORIZONS = (5, 10, 20)
EVENT_NOTIONAL_USD = 10_000.0
MIN_MEDIAN_DOLLAR_VOLUME = 50_000_000.0
MIN_ENTRY_CLOSE = 8.0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def _summary(values: list[float]) -> dict[str, Any]:
    clean = sorted(value for value in values if value is not None and math.isfinite(value))
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "p10": None,
            "p25": None,
            "p75": None,
            "p90": None,
        }

    def pct(q: float) -> float:
        return clean[int(round((len(clean) - 1) * q))]

    return {
        "count": len(clean),
        "avg": _round(statistics.mean(clean)),
        "median": _round(statistics.median(clean)),
        "win_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "p10": _round(pct(0.10)),
        "p25": _round(pct(0.25)),
        "p75": _round(pct(0.75)),
        "p90": _round(pct(0.90)),
    }


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        normalized = []
        for row in rows:
            normalized.append(
                {
                    "date": str(row.get("Date") or row.get("date"))[:10],
                    "open": float(row.get("Open") or row.get("open") or 0),
                    "high": float(row.get("High") or row.get("high") or 0),
                    "low": float(row.get("Low") or row.get("low") or 0),
                    "close": float(row.get("Close") or row.get("close") or 0),
                    "volume": float(row.get("Volume") or row.get("volume") or 0),
                }
            )
        out[str(ticker).upper()] = sorted(normalized, key=lambda item: item["date"])
    return out


def _index_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _entry_features(rows: list[dict[str, Any]], entry_date: str) -> dict[str, Any]:
    idx = _index_on_or_after(rows, entry_date)
    if idx is None:
        return {"covered": False}
    entry = rows[idx]
    prior = rows[max(0, idx - 20) : idx]
    dollar_volumes = [row["close"] * row["volume"] for row in prior if row["close"] and row["volume"]]
    median_dollar_volume = statistics.median(dollar_volumes) if dollar_volumes else None
    forward: dict[str, Any] = {}
    for horizon in HORIZONS:
        end_idx = idx + horizon
        if end_idx < len(rows) and entry["open"] > 0:
            forward[f"fwd_{horizon}d_return"] = rows[end_idx]["close"] / entry["open"] - 1.0
        else:
            forward[f"fwd_{horizon}d_return"] = None
    return {
        "covered": True,
        "entry_date_used": entry["date"],
        "entry_open": entry["open"],
        "entry_close": entry["close"],
        "median_20d_dollar_volume": median_dollar_volume,
        "liquidity_pass": bool(
            median_dollar_volume is not None
            and median_dollar_volume >= MIN_MEDIAN_DOLLAR_VOLUME
            and entry["close"] >= MIN_ENTRY_CLOSE
        ),
        **forward,
    }


def _baseline_context(window: str) -> dict[str, Any]:
    payload = _load_json(BASELINE_FILES[window])
    trades = [
        trade
        for trade in payload.get("trades", [])
        if trade.get("strategy") in {"trend_long", "breakout_long"}
    ]
    by_day: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        day = str(trade.get("entry_date") or "")[:10]
        if day:
            by_day.setdefault(day, []).append(trade)
    return {
        "metrics": {
            "expected_value_score": payload.get("expected_value_score"),
            "sharpe_daily": payload.get("sharpe_daily"),
            "total_pnl": payload.get("total_pnl"),
            "max_drawdown_pct": payload.get("max_drawdown_pct"),
            "win_rate": payload.get("win_rate"),
            "trade_count": payload.get("total_trades") or payload.get("trade_count"),
            "survival_rate": payload.get("survival_rate"),
        },
        "trades": trades,
        "by_day": by_day,
        "tickers": {str(trade.get("ticker")).upper() for trade in trades if trade.get("ticker")},
        "touchpoints": {
            (str(trade.get("ticker")).upper(), str(trade.get("entry_date") or "")[:10])
            for trade in trades
            if trade.get("ticker") and trade.get("entry_date")
        },
    }


def _event_rows(bundle: dict[str, Any], window: str) -> list[dict[str, Any]]:
    overlay = ((bundle.get("event_overlay") or {}).get(window) or {})
    rows = []
    for raw in overlay.get("event_trades") or []:
        row = dict(raw)
        row["window"] = window
        row["return_from_pnl"] = (float(row.get("pnl") or 0.0) / EVENT_NOTIONAL_USD)
        rows.append(row)
    return rows


def _analyze_window(window: str, bundle: dict[str, Any]) -> dict[str, Any]:
    snapshot = _load_snapshot(SNAPSHOT_FILES[window])
    baseline = _baseline_context(window)
    events = _event_rows(bundle, window)
    enriched = []
    source_counts: Counter[str] = Counter()
    overlap_same_day = 0
    overlap_ticker_any = 0
    scarce_values = []
    same_day_core_values = []

    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        entry_date = str(event.get("entry_date") or "")[:10]
        source_counts[str(event.get("source") or "unknown")] += 1
        features = _entry_features(snapshot.get(ticker, []), entry_date)
        same_day_core = baseline["by_day"].get(entry_date, [])
        same_day_core_avg_pnl = None
        if same_day_core:
            overlap_same_day += int(any(str(trade.get("ticker")).upper() == ticker for trade in same_day_core))
            same_day_core_avg_pnl = statistics.mean(float(trade.get("pnl") or 0.0) for trade in same_day_core)
            same_day_core_values.append(same_day_core_avg_pnl)
        if ticker in baseline["tickers"]:
            overlap_ticker_any += 1
        scarce_value = None
        if same_day_core_avg_pnl is not None:
            scarce_value = float(event.get("pnl") or 0.0) - same_day_core_avg_pnl
            scarce_values.append(scarce_value)
        enriched.append(
            {
                **event,
                "same_day_core_trade_count": len(same_day_core),
                "same_ticker_same_day_ab_overlap": (ticker, entry_date) in baseline["touchpoints"],
                "ticker_seen_in_window_ab_trades": ticker in baseline["tickers"],
                "same_day_core_avg_pnl": _round(same_day_core_avg_pnl, 2) if same_day_core_avg_pnl is not None else None,
                "scarce_slot_value_vs_same_day_core_avg_pnl": _round(scarce_value, 2)
                if scarce_value is not None
                else None,
                **{key: _round(value) if isinstance(value, float) else value for key, value in features.items()},
            }
        )

    forward_returns = {
        f"fwd_{horizon}d_return": _summary(
            [
                float(row[f"fwd_{horizon}d_return"])
                for row in enriched
                if row.get(f"fwd_{horizon}d_return") is not None
            ]
        )
        for horizon in HORIZONS
    }
    selected_count = len(enriched)
    covered_count = sum(1 for row in enriched if row.get("covered"))
    liquid_count = sum(1 for row in enriched if row.get("liquidity_pass"))
    event_pnls = [float(row.get("pnl") or 0.0) for row in enriched]

    return {
        "window": window,
        "date_range": WINDOWS[window],
        "candidate_count": selected_count,
        "unique_tickers": len({row.get("ticker") for row in enriched}),
        "source_counts": dict(source_counts),
        "overlap_with_current_ab": {
            "same_ticker_same_day_count": overlap_same_day,
            "same_ticker_same_day_rate": _round(overlap_same_day / selected_count, 4) if selected_count else None,
            "ticker_seen_in_window_ab_trade_count": overlap_ticker_any,
            "ticker_seen_in_window_ab_trade_rate": _round(overlap_ticker_any / selected_count, 4)
            if selected_count
            else None,
            "same_day_core_trade_days": sum(1 for row in enriched if row.get("same_day_core_trade_count", 0) > 0),
        },
        "data_coverage": {
            "selected_candidates": selected_count,
            "ohlcv_entry_covered": covered_count,
            "ohlcv_entry_coverage_rate": _round(covered_count / selected_count, 4) if selected_count else None,
            "valid_forward_10d": forward_returns["fwd_10d_return"]["count"],
            "valid_forward_20d": forward_returns["fwd_20d_return"]["count"],
        },
        "liquidity": {
            "min_median_20d_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_entry_close": MIN_ENTRY_CLOSE,
            "liquidity_pass_count": liquid_count,
            "liquidity_pass_rate": _round(liquid_count / covered_count, 4) if covered_count else None,
            "median_20d_dollar_volume": _summary(
                [
                    float(row["median_20d_dollar_volume"])
                    for row in enriched
                    if row.get("median_20d_dollar_volume") is not None
                ]
            ),
        },
        "forward_return_distribution": forward_returns,
        "event_trade_pnl_distribution": {
            "pnl_usd": _summary(event_pnls),
            "pnl_per_trade_usd": _round(statistics.mean(event_pnls), 2) if event_pnls else None,
            "win_rate": _round(sum(1 for pnl in event_pnls if pnl > 0) / len(event_pnls), 4) if event_pnls else None,
        },
        "scarce_slot_value": {
            "same_day_comparisons": len(scarce_values),
            "avg_same_day_core_pnl": _round(statistics.mean(same_day_core_values), 2) if same_day_core_values else None,
            "avg_event_minus_same_day_core_avg_pnl": _round(statistics.mean(scarce_values), 2)
            if scarce_values
            else None,
            "positive_replacement_value_rate": _round(
                sum(1 for value in scarce_values if value > 0) / len(scarce_values), 4
            )
            if scarce_values
            else None,
            "event_pnl_per_trade_vs_core_pnl_per_trade": {
                "event_avg_pnl": _round(statistics.mean(event_pnls), 2) if event_pnls else None,
                "core_avg_pnl": _round(statistics.mean(float(trade.get("pnl") or 0.0) for trade in baseline["trades"]), 2)
                if baseline["trades"]
                else None,
            },
        },
        "candidate_rows": enriched,
    }


def main() -> None:
    bundle = _load_json(BUNDLE_JSON)
    windows = {window: _analyze_window(window, bundle) for window in WINDOWS}
    selected_total = sum(row["candidate_count"] for row in windows.values())
    raw_price_ready = (
        int((bundle.get("coverage") or {}).get("form4_price_ready_candidates") or 0)
        + int((bundle.get("coverage") or {}).get("sec_negative_price_ready_candidates") or 0)
        + int(((bundle.get("coverage") or {}).get("sec_governance_coverage") or {}).get("deduped_candidate_count") or 0)
    )
    skipped = sum(
        int(value)
        for value in ((bundle.get("coverage") or {}).get("source_skipped_counts") or {}).values()
        if isinstance(value, int)
    )
    event_avg_values = [
        window["scarce_slot_value"]["event_pnl_per_trade_vs_core_pnl_per_trade"]["event_avg_pnl"]
        for window in windows.values()
        if window["scarce_slot_value"]["event_pnl_per_trade_vs_core_pnl_per_trade"]["event_avg_pnl"] is not None
    ]
    core_avg_values = [
        window["scarce_slot_value"]["event_pnl_per_trade_vs_core_pnl_per_trade"]["core_avg_pnl"]
        for window in windows.values()
        if window["scarce_slot_value"]["event_pnl_per_trade_vs_core_pnl_per_trade"]["core_avg_pnl"] is not None
    ]
    low_overlap_all = all(
        (window["overlap_with_current_ab"]["same_ticker_same_day_rate"] or 0.0) <= 0.10
        for window in windows.values()
    )
    liquidity_ok_all = all((window["liquidity"]["liquidity_pass_rate"] or 0.0) >= 0.80 for window in windows.values())
    positive_forward_10d_windows = sum(
        1
        for window in windows.values()
        if (window["forward_return_distribution"]["fwd_10d_return"]["median"] or 0.0) > 0
    )
    event_beats_core_avg_windows = sum(
        1
        for event_avg, core_avg in zip(event_avg_values, core_avg_values)
        if event_avg is not None and core_avg is not None and event_avg > core_avg
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "universe_scout",
        "status": "observed_only",
        "single_causal_variable": "event-bundle eligible liquidity-filtered universe coverage",
        "hypothesis": (
            "The frozen default-off external event bundle may define an event-sensitive "
            "liquidity-filtered shadow universe with non-overlap, data coverage, liquidity, "
            "forward return quality, and scarce-slot value."
        ),
        "history_guardrail": {
            "exact_event_sensitive_liquidity_universe_already_observed": [
                "exp-20260427-005",
                "exp-20260430-001",
                "exp-20260501-013",
            ],
            "not_repeating": [
                "broad historical-attention-list universe expansion rejected in exp-20260505-009",
                "consumer platform sub-basket simple gates rejected in exp-20260505-020",
                "same-sample event bundle source-composition retuning rejected in exp-20260505-004",
            ],
            "why_this_is_not_duplicate": (
                "This audits the already-frozen default-off event bundle as a universe coverage "
                "surface; it does not retune event thresholds, add FD/Other, or expand the core ticker list."
            ),
        },
        "candidate_count": {
            "price_ready_source_candidates": raw_price_ready,
            "selected_event_trades": selected_total,
            "skipped_by_capacity": skipped,
        },
        "aggregate": {
            "low_same_ticker_same_day_ab_overlap_all_windows": low_overlap_all,
            "liquidity_pass_rate_ge_80pct_all_windows": liquidity_ok_all,
            "positive_median_10d_forward_windows": positive_forward_10d_windows,
            "event_avg_pnl_beats_core_avg_pnl_windows": event_beats_core_avg_windows,
        },
        "survivorship_bias_risk": {
            "risk": "medium",
            "reason": (
                "SEC/Form 4 event rows are point-in-time style artifacts, but OHLCV snapshots and "
                "baseline universe membership are current repository snapshots rather than a fully "
                "audited point-in-time tradable universe."
            ),
        },
        "windows": windows,
        "decision": "observed_only",
        "decision_rationale": (
            "The bundle remains suitable for forward observation, not production universe promotion. "
            "It has strong replay PnL in the source artifact and low same-day A/B overlap here, but "
            "this ticket is an audit of coverage/liquidity/replacement value rather than a new "
            "backtest-enabled production change."
        ),
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
        "related_files": [
            "data/experiments/exp-20260504-049/default_off_event_overlay_bundle.json",
            "data/experiments/exp-20260505-025/event_bundle_direction.json",
            "data/experiments/exp-20260505-025/baseline_late_strong.json",
            "data/experiments/exp-20260505-025/baseline_mid_weak.json",
            "data/experiments/exp-20260505-025/baseline_old_thin.json",
        ],
    }
    _write_json(OUT_JSON, payload)
    print(json.dumps({"wrote": str(OUT_JSON), "selected_event_trades": selected_total}, indent=2))


if __name__ == "__main__":
    main()
