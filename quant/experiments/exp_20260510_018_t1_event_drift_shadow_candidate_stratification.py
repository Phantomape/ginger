"""Shadow-only T+1 event-drift stratification audit for exp-20260510-018.

This runner does not change production behavior. It measures whether archived
trade-news events, stratified only by next-session drift sign versus SPY, expose
non-overlapping forward-return candidates worth future paper observation.
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
EXPERIMENT_ID = "exp-20260510-018"
OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / "exp_20260510_018_t1_event_drift_shadow_candidate_stratification.json"
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "baseline": "data/experiments/exp-20260505-025/baseline_late_strong.json",
                "entry_events": "data/experiments/exp-20260510-018/entry_candidate_events_late_strong.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "baseline": "data/experiments/exp-20260505-025/baseline_mid_weak.json",
                "entry_events": "data/experiments/exp-20260510-018/entry_candidate_events_mid_weak.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "baseline": "data/experiments/exp-20260505-025/baseline_old_thin.json",
                "entry_events": "data/experiments/exp-20260510-018/entry_candidate_events_old_thin.json",
            },
        ),
    ]
)

LATEST_ACCEPTED_METRICS = {
    "late_strong": {
        "expected_value_score": 4.2340,
        "sharpe_daily": 4.50,
        "total_pnl": 94086.91,
        "total_return_pct": 0.9409,
        "max_drawdown_pct": 0.0548,
        "win_rate": 0.7895,
        "trade_count": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.6689,
        "sharpe_daily": 2.70,
        "total_pnl": 61813.40,
        "total_return_pct": 0.6181,
        "max_drawdown_pct": 0.0941,
        "win_rate": 0.5238,
        "trade_count": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3853,
        "sharpe_daily": 1.35,
        "total_pnl": 28544.11,
        "total_return_pct": 0.2854,
        "max_drawdown_pct": 0.0815,
        "win_rate": 0.4091,
        "trade_count": 22,
        "survival_rate": 0.9167,
    },
}

FORWARD_HORIZONS = (1, 5, 10, 20)
SHADOW_NOTIONAL_USD = 10_000.0
EVENT_ARCHIVE_GLOBS = ("clean_news_*.json", "clean_trade_news_*.json")
EXCLUDED_TICKERS = {
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


def _summary(values: list[float | None]) -> dict[str, Any]:
    clean = sorted(float(value) for value in values if isinstance(value, (int, float)) and math.isfinite(value))
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


def _date_from_archive(path: Path) -> str | None:
    raw = path.stem.rsplit("_", 1)[-1]
    if len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _row_date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def _as_float(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
        return float(raw)
    return None


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in (ohlcv or {}).items():
        normalized = []
        for row in rows:
            normalized.append(
                {
                    "date": _row_date(row),
                    "open": _as_float(row, "Open"),
                    "high": _as_float(row, "High"),
                    "low": _as_float(row, "Low"),
                    "close": _as_float(row, "Close"),
                    "volume": _as_float(row, "Volume"),
                }
            )
        out[str(ticker).upper()] = sorted(normalized, key=lambda item: item["date"])
    return out


def _index_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _return_between(rows: list[dict[str, Any]], start_idx: int, end_idx: int, start_field: str = "close") -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_value = rows[start_idx].get(start_field)
    end_value = rows[end_idx].get("close")
    if not isinstance(start_value, (int, float)) or not isinstance(end_value, (int, float)):
        return None
    if start_value <= 0:
        return None
    return float(end_value) / float(start_value) - 1.0


def _load_events() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    events_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    archive_dates = []
    item_count = 0
    seen_event_keys = set()
    for glob_pattern in EVENT_ARCHIVE_GLOBS:
        for path in sorted((REPO_ROOT / "data").glob(glob_pattern)):
            archive_date = _date_from_archive(path)
            if archive_date is None:
                continue
            archive_dates.append(archive_date)
            payload = _load_json(path)
            if not isinstance(payload, list):
                continue
            for item in payload:
                if not isinstance(item, dict):
                    continue
                item_count += 1
                for raw_ticker in item.get("tickers") or []:
                    ticker = str(raw_ticker).upper()
                    if not ticker or ticker in EXCLUDED_TICKERS:
                        continue
                    event_key = (
                        archive_date,
                        ticker,
                        str(item.get("title") or "")[:180],
                        str(item.get("url") or "")[:180],
                    )
                    if event_key in seen_event_keys:
                        continue
                    seen_event_keys.add(event_key)
                    events_by_ticker[ticker].append(
                        {
                            "archive_date": archive_date,
                            "published_at": item.get("published_at"),
                            "source": item.get("source"),
                            "tier": item.get("tier"),
                            "ticker": ticker,
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "archive_glob": glob_pattern,
                        }
                    )
    coverage = {
        "archive_file_count": len(set(archive_dates)),
        "archive_date_min": min(archive_dates) if archive_dates else None,
        "archive_date_max": max(archive_dates) if archive_dates else None,
        "raw_event_items": item_count,
        "tickers_with_events": len(events_by_ticker),
        "event_rows_after_ticker_exclusions": sum(len(rows) for rows in events_by_ticker.values()),
        "event_archive_globs": [f"data/{pattern}" for pattern in EVENT_ARCHIVE_GLOBS],
    }
    return events_by_ticker, coverage


def _load_baseline_context(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"trades": [], "by_day": {}, "touchpoints": set(), "tickers": set(), "source_file": str(path)}
    payload = _load_json(path)
    trades = [
        trade
        for trade in payload.get("trades", [])
        if trade.get("strategy") in {"trend_long", "breakout_long"}
    ]
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    touchpoints = set()
    tickers = set()
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        day = str(trade.get("entry_date") or "")[:10]
        if ticker:
            tickers.add(ticker)
        if day:
            by_day[day].append(trade)
        if ticker and day:
            touchpoints.add((ticker, day))
    return {
        "trades": trades,
        "by_day": by_day,
        "touchpoints": touchpoints,
        "tickers": tickers,
        "source_file": str(path.relative_to(REPO_ROOT)),
    }


def _load_entry_pressure(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"by_date": {}, "reason_counts": {}, "source_file": str(path)}
    payload = _load_json(path)
    attribution = payload.get("entry_execution_attribution") or {}
    return {
        "by_date": attribution.get("by_date") or {},
        "reason_counts": attribution.get("reason_counts") or {},
        "candidate_events": attribution.get("candidate_events"),
        "source_file": str(path.relative_to(REPO_ROOT)),
    }


def _drift_bucket(t1_return: float | None, spy_t1_return: float | None) -> str:
    if t1_return is None or spy_t1_return is None:
        return "immature_or_missing_t1"
    if t1_return > 0 and t1_return > spy_t1_return:
        return "positive_t1_excess_drift"
    if t1_return > 0:
        return "positive_t1_absolute_only"
    return "negative_or_zero_t1_drift"


def _dedupe_event_key(event: dict[str, Any], event_date: str) -> tuple[str, str, str]:
    return (event["ticker"], event_date, str(event.get("title") or "")[:140])


def _build_event_rows(
    snapshot: dict[str, list[dict[str, Any]]],
    events_by_ticker: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    baseline: dict[str, Any],
    pressure: dict[str, Any],
) -> list[dict[str, Any]]:
    spy_rows = snapshot.get("SPY", [])
    out = []
    seen = set()
    for ticker, events in events_by_ticker.items():
        ticker_rows = snapshot.get(ticker)
        if not ticker_rows or len(ticker_rows) < 30 or not spy_rows:
            continue
        for event in events:
            if not (cfg["start"] <= event["archive_date"] <= cfg["end"]):
                continue
            event_idx = _index_on_or_after(ticker_rows, event["archive_date"])
            spy_idx = _index_on_or_after(spy_rows, event["archive_date"])
            if event_idx is None or spy_idx is None:
                continue
            event_date = ticker_rows[event_idx]["date"]
            key = _dedupe_event_key(event, event_date)
            if key in seen:
                continue
            seen.add(key)
            t1_idx = event_idx + 1
            entry_idx = event_idx + 2
            spy_t1_idx = spy_idx + 1
            t1_return = _return_between(ticker_rows, event_idx, t1_idx)
            spy_t1_return = _return_between(spy_rows, spy_idx, spy_t1_idx)
            bucket = _drift_bucket(t1_return, spy_t1_return)
            entry_date = ticker_rows[entry_idx]["date"] if entry_idx < len(ticker_rows) else None
            entry_open = ticker_rows[entry_idx].get("open") if entry_idx < len(ticker_rows) else None

            forward_returns = {}
            shadow_pnls = {}
            if entry_date is not None and isinstance(entry_open, (int, float)) and entry_open > 0:
                for horizon in FORWARD_HORIZONS:
                    fwd = _return_between(ticker_rows, entry_idx, entry_idx + horizon, start_field="open")
                    forward_returns[f"fwd_{horizon}d_return"] = _round(fwd)
                    shadow_pnls[f"fwd_{horizon}d_pnl_proxy"] = (
                        _round(fwd * SHADOW_NOTIONAL_USD, 2) if fwd is not None else None
                    )
            else:
                for horizon in FORWARD_HORIZONS:
                    forward_returns[f"fwd_{horizon}d_return"] = None
                    shadow_pnls[f"fwd_{horizon}d_pnl_proxy"] = None

            same_day_core = baseline["by_day"].get(entry_date, []) if entry_date else []
            same_day_core_pnls = [
                float(trade.get("pnl"))
                for trade in same_day_core
                if isinstance(trade.get("pnl"), (int, float)) and math.isfinite(float(trade.get("pnl")))
            ]
            same_day_core_avg_pnl = statistics.mean(same_day_core_pnls) if same_day_core_pnls else None
            fwd_10_pnl = shadow_pnls.get("fwd_10d_pnl_proxy")
            replacement_delta = (
                fwd_10_pnl - same_day_core_avg_pnl
                if isinstance(fwd_10_pnl, (int, float)) and same_day_core_avg_pnl is not None
                else None
            )
            entry_pressure = pressure["by_date"].get(entry_date, {}) if entry_date else {}
            scarce_pressure_count = 0
            if isinstance(entry_pressure, dict):
                scarce_pressure_count = int(entry_pressure.get("slot_sliced") or 0) + int(
                    entry_pressure.get("scarce_slot_breakout_deferred") or 0
                )

            out.append(
                {
                    "ticker": ticker,
                    "event_archive_date": event["archive_date"],
                    "event_trading_date": event_date,
                    "t1_date": ticker_rows[t1_idx]["date"] if t1_idx < len(ticker_rows) else None,
                    "shadow_entry_date": entry_date,
                    "source": event.get("source"),
                    "tier": event.get("tier"),
                    "archive_glob": event.get("archive_glob"),
                    "title": event.get("title"),
                    "url": event.get("url"),
                    "t1_return": _round(t1_return),
                    "spy_t1_return": _round(spy_t1_return),
                    "t1_excess_return_vs_spy": _round(
                        t1_return - spy_t1_return
                        if isinstance(t1_return, (int, float)) and isinstance(spy_t1_return, (int, float))
                        else None
                    ),
                    "drift_bucket": bucket,
                    "same_day_core_trade_count": len(same_day_core),
                    "same_day_ab_overlap": bool(same_day_core),
                    "same_ticker_same_day_ab_overlap": (ticker, entry_date) in baseline["touchpoints"]
                    if entry_date
                    else False,
                    "ticker_seen_in_baseline_window": ticker in baseline["tickers"],
                    "entry_day_slot_pressure_count": scarce_pressure_count,
                    "entry_day_has_slot_pressure": scarce_pressure_count > 0,
                    "same_day_core_avg_pnl": _round(same_day_core_avg_pnl, 2)
                    if same_day_core_avg_pnl is not None
                    else None,
                    "scarce_slot_value_vs_same_day_core_avg_pnl_10d": _round(replacement_delta, 2)
                    if replacement_delta is not None
                    else None,
                    **forward_returns,
                    **shadow_pnls,
                }
            )
    return sorted(
        out,
        key=lambda row: (
            row["event_trading_date"],
            row["ticker"],
            row.get("title") or "",
        ),
    )


def _summarize_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fwd_10_pnls = [row.get("fwd_10d_pnl_proxy") for row in rows]
    replacement_values = [row.get("scarce_slot_value_vs_same_day_core_avg_pnl_10d") for row in rows]
    return {
        "candidate_count": len(rows),
        "unique_tickers": len({row["ticker"] for row in rows}),
        "same_day_ab_overlap_count": sum(1 for row in rows if row["same_day_ab_overlap"]),
        "same_day_ab_overlap_rate": _round(
            sum(1 for row in rows if row["same_day_ab_overlap"]) / len(rows), 4
        )
        if rows
        else None,
        "same_ticker_same_day_ab_overlap_count": sum(
            1 for row in rows if row["same_ticker_same_day_ab_overlap"]
        ),
        "entry_day_slot_pressure_count": sum(1 for row in rows if row["entry_day_has_slot_pressure"]),
        "entry_day_slot_pressure_rate": _round(
            sum(1 for row in rows if row["entry_day_has_slot_pressure"]) / len(rows), 4
        )
        if rows
        else None,
        "ticker_counts": Counter(row["ticker"] for row in rows).most_common(10),
        "forward_return_distribution": {
            f"fwd_{horizon}d_return": _summary([row.get(f"fwd_{horizon}d_return") for row in rows])
            for horizon in FORWARD_HORIZONS
        },
        "shadow_10d_pnl_proxy": _summary(fwd_10_pnls),
        "scarce_slot_value_vs_same_day_core_avg_pnl_10d": _summary(replacement_values),
    }


def _analyze_window(label: str, cfg: dict[str, str], events_by_ticker: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    snapshot = _load_snapshot(REPO_ROOT / cfg["snapshot"])
    baseline = _load_baseline_context(REPO_ROOT / cfg["baseline"])
    pressure = _load_entry_pressure(REPO_ROOT / cfg["entry_events"])
    rows = _build_event_rows(snapshot, events_by_ticker, cfg, baseline, pressure)
    by_bucket = {
        bucket: _summarize_bucket([row for row in rows if row["drift_bucket"] == bucket])
        for bucket in [
            "positive_t1_excess_drift",
            "positive_t1_absolute_only",
            "negative_or_zero_t1_drift",
            "immature_or_missing_t1",
        ]
    }
    candidate_rows = [row for row in rows if row["drift_bucket"] == "positive_t1_excess_drift"]
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": LATEST_ACCEPTED_METRICS[label],
        "overlap_baseline_trade_source": baseline["source_file"],
        "entry_pressure_source": pressure["source_file"],
        "entry_pressure_reason_counts": pressure["reason_counts"],
        "event_rows_total": len(rows),
        "event_rows_unique_tickers": len({row["ticker"] for row in rows}),
        "drift_bucket_summary": by_bucket,
        "shadow_candidate_definition": "positive_t1_excess_drift rows only; this is an audit label, not a production rule",
        "shadow_candidate_count": len(candidate_rows),
        "shadow_candidate_forward_10d": _summary([row.get("fwd_10d_return") for row in candidate_rows]),
        "shadow_candidate_non_overlap_forward_10d": _summary(
            [row.get("fwd_10d_return") for row in candidate_rows if not row["same_day_ab_overlap"]]
        ),
        "shadow_candidate_scarce_slot_value": _summary(
            [row.get("scarce_slot_value_vs_same_day_core_avg_pnl_10d") for row in candidate_rows]
        ),
        "shadow_candidate_rows": candidate_rows,
    }


def main() -> None:
    events_by_ticker, event_coverage = _load_events()
    windows = OrderedDict(
        (label, _analyze_window(label, cfg, events_by_ticker)) for label, cfg in WINDOWS.items()
    )
    aggregate_candidate_rows = [
        row
        for window in windows.values()
        for row in window["shadow_candidate_rows"]
    ]
    aggregate_candidate_count = len(aggregate_candidate_rows)
    positive_windows = sum(
        1
        for window in windows.values()
        if (window["shadow_candidate_forward_10d"]["avg"] or 0.0) > 0
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_discovery",
        "status": "observed_only",
        "change_type": "new_strategy_shadow",
        "single_causal_variable": "T1 event drift shadow candidate stratification",
        "hypothesis": (
            "A T+1 event-drift stratification can identify post-event continuation candidates that are "
            "less overlapping with current A/B entries without repeating rejected PEAD threshold retuning."
        ),
        "history_guardrail": {
            "blocked_repeat": "exp-20260509-020 rejected PEAD-like threshold recipe",
            "blocked_recipe": "Do not retune +1% event reaction, 1.5x volume confirmation, or 10-trading-day PEAD hold.",
            "this_run_difference": (
                "Uses archived clean_trade_news events and a descriptive T+1 drift sign/excess-vs-SPY "
                "stratification. No reaction magnitude threshold, volume threshold, holding-period retune, "
                "ranking rule, or production adapter is changed."
            ),
        },
        "data_sources": {
            "event_coverage": event_coverage,
            "windows": WINDOWS,
            "latest_accepted_metric_source": "docs/backtesting.md exp-20260510-015 accepted fixed-window table",
            "overlap_trade_source_note": (
                "Overlap uses available local baseline trade JSONs from exp-20260505-025, so overlap is "
                "feasible but not a claim of exact latest-stack trade identity."
            ),
            "entry_pressure_note": (
                "Slot pressure context is read from existing exp-20260510-018 entry_candidate_events artifacts; "
                "those files are not modified by this run."
            ),
        },
        "parameters": {
            "event_archive_globs": [f"data/{pattern}" for pattern in EVENT_ARCHIVE_GLOBS],
            "drift_variable": "T+1 close-to-close event ticker return minus SPY T+1 close-to-close return",
            "candidate_bucket": "positive_t1_excess_drift",
            "forward_horizons_trading_days": list(FORWARD_HORIZONS),
            "shadow_notional_usd": SHADOW_NOTIONAL_USD,
            "llm_used": False,
            "production_promotion_allowed": False,
        },
        "windows": windows,
        "aggregate": {
            "shadow_candidate_count": aggregate_candidate_count,
            "positive_avg_10d_windows": positive_windows,
            "forward_10d": _summary([row.get("fwd_10d_return") for row in aggregate_candidate_rows]),
            "non_overlap_forward_10d": _summary(
                [row.get("fwd_10d_return") for row in aggregate_candidate_rows if not row["same_day_ab_overlap"]]
            ),
            "slot_pressure_rate": _round(
                sum(1 for row in aggregate_candidate_rows if row["entry_day_has_slot_pressure"])
                / aggregate_candidate_count,
                4,
            )
            if aggregate_candidate_count
            else None,
            "aggregation_note": (
                "Aggregate forward summaries are computed from all positive_t1_excess_drift shadow rows."
            ),
        },
        "decision": "observed_only",
        "decision_rationale": (
            "This is a shadow-only stratification artifact. It creates no valid before/after strategy "
            "comparison and should not be promoted to production."
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
        "next_evidence_needed": [
            "Forward paper observations for the exact positive_t1_excess_drift bucket.",
            "A current-stack overlap manifest if this becomes a promotion candidate.",
            "No nearby PEAD threshold, volume-confirmation, or hold-day sweeps without new semantic event-quality evidence.",
        ],
        "related_files": [
            "quant/experiments/exp_20260510_018_t1_event_drift_shadow_candidate_stratification.py",
            "data/experiments/exp-20260510-018/exp_20260510_018_t1_event_drift_shadow_candidate_stratification.json",
            "docs/experiments/tickets/exp-20260510-018.json",
            "docs/experiments/logs/exp-20260510-018.json",
        ],
    }
    _write_json(OUT_JSON, payload)
    print(
        json.dumps(
            {
                "wrote": str(OUT_JSON.relative_to(REPO_ROOT)),
                "shadow_candidate_count": aggregate_candidate_count,
                "positive_avg_10d_windows": positive_windows,
                "status": "observed_only",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
