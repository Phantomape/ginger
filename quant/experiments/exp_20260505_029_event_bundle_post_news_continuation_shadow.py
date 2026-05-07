"""exp-20260505-029 event-bundle post-news continuation shadow audit.

This is an observed-only alpha_discovery runner. It does not alter production
signals, sizing, ranking, exits, or portfolio constraints.
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
EXPERIMENT_ID = "exp-20260505-029"
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260505_029_event_bundle_post_news_continuation_shadow.json"
)

BUNDLE_JSON = REPO_ROOT / "data" / "experiments" / "exp-20260504-049" / "default_off_event_overlay_bundle.json"
BASELINE_FILES = OrderedDict(
    [
        ("late_strong", REPO_ROOT / "data" / "experiments" / "exp-20260505-025" / "baseline_late_strong.json"),
        ("mid_weak", REPO_ROOT / "data" / "experiments" / "exp-20260505-025" / "baseline_mid_weak.json"),
        ("old_thin", REPO_ROOT / "data" / "experiments" / "exp-20260505-025" / "baseline_old_thin.json"),
    ]
)
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
SHADOW_NOTIONAL_USD = 10_000.0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
                    "open": float(row.get("Open") or row.get("open") or 0.0),
                    "high": float(row.get("High") or row.get("high") or 0.0),
                    "low": float(row.get("Low") or row.get("low") or 0.0),
                    "close": float(row.get("Close") or row.get("close") or 0.0),
                    "volume": float(row.get("Volume") or row.get("volume") or 0.0),
                }
            )
        out[str(ticker).upper()] = sorted(normalized, key=lambda item: item["date"])
    return out


def _index_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


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
        rows.append(row)
    return rows


def _continuation_candidate(
    event: dict[str, Any],
    ticker_rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ticker = str(event.get("ticker") or "").upper()
    event_date = str(event.get("entry_date") or "")[:10]
    event_idx = _index_on_or_after(ticker_rows, event_date)
    spy_event_idx = _index_on_or_after(spy_rows, event_date)
    if ticker and event_idx is None:
        return None
    if event_idx is None or spy_event_idx is None:
        return None
    follow_idx = event_idx + 1
    entry_idx = event_idx + 2
    spy_follow_idx = spy_event_idx + 1
    if follow_idx >= len(ticker_rows) or entry_idx >= len(ticker_rows) or spy_follow_idx >= len(spy_rows):
        return None

    event_row = ticker_rows[event_idx]
    follow_row = ticker_rows[follow_idx]
    entry_row = ticker_rows[entry_idx]
    spy_event_row = spy_rows[spy_event_idx]
    spy_follow_row = spy_rows[spy_follow_idx]
    if event_row["close"] <= 0 or spy_event_row["close"] <= 0:
        return None

    follow_return = follow_row["close"] / event_row["close"] - 1.0
    spy_follow_return = spy_follow_row["close"] / spy_event_row["close"] - 1.0
    if follow_return <= 0 or follow_return <= spy_follow_return:
        return None

    forward: dict[str, Any] = {}
    for horizon in HORIZONS:
        end_idx = entry_idx + horizon
        if end_idx < len(ticker_rows) and entry_row["open"] > 0:
            forward[f"fwd_{horizon}d_return"] = ticker_rows[end_idx]["close"] / entry_row["open"] - 1.0
        else:
            forward[f"fwd_{horizon}d_return"] = None
    fwd_10 = forward.get("fwd_10d_return")
    return {
        "ticker": ticker,
        "source": event.get("source") or "unknown",
        "event_entry_date": event_date,
        "follow_through_date": follow_row["date"],
        "shadow_entry_date": entry_row["date"],
        "event_close": event_row["close"],
        "follow_through_close": follow_row["close"],
        "shadow_entry_open": entry_row["open"],
        "follow_through_return": follow_return,
        "spy_follow_through_return": spy_follow_return,
        "rs_follow_through_return": follow_return - spy_follow_return,
        "source_event_pnl": float(event.get("pnl") or 0.0),
        "shadow_10d_pnl_proxy": fwd_10 * SHADOW_NOTIONAL_USD if fwd_10 is not None else None,
        **forward,
    }


def _analyze_window(window: str, bundle: dict[str, Any]) -> dict[str, Any]:
    snapshot = _load_snapshot(SNAPSHOT_FILES[window])
    baseline = _baseline_context(window)
    spy_rows = snapshot.get("SPY", [])
    source_events = _event_rows(bundle, window)
    candidates = []
    source_counts: Counter[str] = Counter()
    rejected_no_continuation = 0
    same_ticker_same_day_overlap = 0
    ticker_seen_in_ab = 0
    same_day_core_values = []
    scarce_values = []

    for event in source_events:
        ticker = str(event.get("ticker") or "").upper()
        source_counts[str(event.get("source") or "unknown")] += 1
        candidate = _continuation_candidate(event, snapshot.get(ticker, []), spy_rows)
        if candidate is None:
            rejected_no_continuation += 1
            continue
        shadow_entry_date = candidate["shadow_entry_date"]
        same_day_core = baseline["by_day"].get(shadow_entry_date, [])
        same_day_core_avg_pnl = None
        if same_day_core:
            same_day_core_avg_pnl = statistics.mean(float(trade.get("pnl") or 0.0) for trade in same_day_core)
            same_day_core_values.append(same_day_core_avg_pnl)
        same_ticker_overlap = (ticker, shadow_entry_date) in baseline["touchpoints"]
        same_ticker_same_day_overlap += int(same_ticker_overlap)
        ticker_was_seen = ticker in baseline["tickers"]
        ticker_seen_in_ab += int(ticker_was_seen)
        scarce_value = None
        if same_day_core_avg_pnl is not None and candidate["shadow_10d_pnl_proxy"] is not None:
            scarce_value = candidate["shadow_10d_pnl_proxy"] - same_day_core_avg_pnl
            scarce_values.append(scarce_value)
        candidates.append(
            {
                **{
                    key: _round(value) if isinstance(value, float) else value
                    for key, value in candidate.items()
                },
                "same_day_core_trade_count": len(same_day_core),
                "same_ticker_same_day_ab_overlap": same_ticker_overlap,
                "ticker_seen_in_window_ab_trades": ticker_was_seen,
                "same_day_core_avg_pnl": _round(same_day_core_avg_pnl, 2)
                if same_day_core_avg_pnl is not None
                else None,
                "scarce_slot_value_vs_same_day_core_avg_pnl": _round(scarce_value, 2)
                if scarce_value is not None
                else None,
            }
        )

    forward_returns = {
        f"fwd_{horizon}d_return": _summary(
            [
                float(row[f"fwd_{horizon}d_return"])
                for row in candidates
                if row.get(f"fwd_{horizon}d_return") is not None
            ]
        )
        for horizon in HORIZONS
    }
    shadow_pnls = [
        float(row["shadow_10d_pnl_proxy"])
        for row in candidates
        if row.get("shadow_10d_pnl_proxy") is not None
    ]
    count = len(candidates)
    return {
        "window": window,
        "date_range": WINDOWS[window],
        "baseline_metrics": baseline["metrics"],
        "source_event_count": len(source_events),
        "candidate_count": count,
        "rejected_no_one_day_continuation_count": rejected_no_continuation,
        "unique_tickers": len({row["ticker"] for row in candidates}),
        "source_counts_before_continuation": dict(source_counts),
        "source_counts_after_continuation": dict(Counter(row["source"] for row in candidates)),
        "overlap_with_current_ab": {
            "same_ticker_same_day_count": same_ticker_same_day_overlap,
            "same_ticker_same_day_rate": _round(same_ticker_same_day_overlap / count, 4) if count else None,
            "ticker_seen_in_window_ab_trade_count": ticker_seen_in_ab,
            "ticker_seen_in_window_ab_trade_rate": _round(ticker_seen_in_ab / count, 4) if count else None,
            "same_day_core_trade_days": sum(1 for row in candidates if row["same_day_core_trade_count"] > 0),
        },
        "forward_return_distribution": forward_returns,
        "shadow_10d_pnl_proxy_distribution": {
            "notional_usd": SHADOW_NOTIONAL_USD,
            "pnl_usd": _summary(shadow_pnls),
            "avg_pnl_per_candidate": _round(statistics.mean(shadow_pnls), 2) if shadow_pnls else None,
            "win_rate": _round(sum(1 for pnl in shadow_pnls if pnl > 0) / len(shadow_pnls), 4)
            if shadow_pnls
            else None,
        },
        "scarce_slot_value": {
            "same_day_comparisons": len(scarce_values),
            "avg_same_day_core_pnl": _round(statistics.mean(same_day_core_values), 2)
            if same_day_core_values
            else None,
            "avg_shadow_minus_same_day_core_avg_pnl": _round(statistics.mean(scarce_values), 2)
            if scarce_values
            else None,
            "positive_replacement_value_rate": _round(
                sum(1 for value in scarce_values if value > 0) / len(scarce_values), 4
            )
            if scarce_values
            else None,
            "shadow_avg_pnl_vs_core_avg_pnl": {
                "shadow_avg_10d_pnl_proxy": _round(statistics.mean(shadow_pnls), 2) if shadow_pnls else None,
                "core_avg_pnl": _round(statistics.mean(float(trade.get("pnl") or 0.0) for trade in baseline["trades"]), 2)
                if baseline["trades"]
                else None,
            },
        },
        "candidate_rows": candidates,
    }


def main() -> None:
    bundle = _load_json(BUNDLE_JSON)
    windows = OrderedDict((window, _analyze_window(window, bundle)) for window in WINDOWS)
    aggregate_candidates = sum(item["candidate_count"] for item in windows.values())
    positive_median_10d_windows = sum(
        1
        for item in windows.values()
        if (item["forward_return_distribution"]["fwd_10d_return"]["median"] or 0.0) > 0
    )
    low_overlap_windows = sum(
        1
        for item in windows.values()
        if (item["overlap_with_current_ab"]["same_ticker_same_day_rate"] or 0.0) <= 0.10
    )
    positive_replacement_windows = sum(
        1
        for item in windows.values()
        if (item["scarce_slot_value"]["avg_shadow_minus_same_day_core_avg_pnl"] or 0.0) > 0
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_discovery",
        "status": "observed_only",
        "change_type": "new_strategy_shadow",
        "single_causal_variable": "event-bundle confirmed post-news continuation entry pattern",
        "hypothesis": (
            "A frozen event-bundle confirmed post-news continuation shadow entry may identify scarce "
            "non-overlapping candidates with better forward returns than the previously rejected broad "
            "clean-news continuation sample."
        ),
        "history_guardrail": {
            "prior_exact_mechanism": "exp-20260427-003 broad clean-news post-news continuation",
            "prior_result": (
                "58 late_strong candidates, zero mid_weak/old_thin candidates, 10d average "
                "-0.9682%, 36.84% 10d win rate; no production replay without broader coverage or "
                "stronger discriminator."
            ),
            "why_this_is_not_duplicate": (
                "This uses only the already-frozen default-off external event bundle and adds one "
                "post-event follow-through requirement. It does not retune news keywords, event "
                "sources, source thresholds, holding periods, or production rules."
            ),
        },
        "shadow_entry_definition": {
            "source": "data/experiments/exp-20260504-049/default_off_event_overlay_bundle.json",
            "event_source_frozen": True,
            "entry_pattern": (
                "For each frozen event-bundle candidate, require the next trading session close to "
                "be above the event entry close and to beat SPY over the same one-session interval; "
                "shadow entry is the following session open."
            ),
            "forward_return_horizons_trading_days": list(HORIZONS),
            "shadow_notional_usd": SHADOW_NOTIONAL_USD,
            "llm_used": False,
        },
        "aggregate": {
            "candidate_count": aggregate_candidates,
            "positive_median_10d_forward_windows": positive_median_10d_windows,
            "low_same_ticker_same_day_ab_overlap_windows": low_overlap_windows,
            "positive_same_day_replacement_value_windows": positive_replacement_windows,
        },
        "windows": windows,
        "decision": "observed_only",
        "decision_rationale": (
            "Shadow-only audit. The pattern is not production-promoted because it has sparse same-day "
            "replacement comparisons and no production/backtest parity adapter. Use the artifact as "
            "candidate evidence for future forward paper observation only."
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
            "docs/experiments/tickets/exp-20260505-029.json",
            "data/experiments/exp-20260504-049/default_off_event_overlay_bundle.json",
            "data/experiments/exp-20260505-025/baseline_late_strong.json",
            "data/experiments/exp-20260505-025/baseline_mid_weak.json",
            "data/experiments/exp-20260505-025/baseline_old_thin.json",
        ],
    }
    _write_json(OUT_JSON, payload)
    print(json.dumps({"wrote": str(OUT_JSON), "candidate_count": aggregate_candidates}, indent=2))


if __name__ == "__main__":
    main()
