"""exp-20260511-100: SEC financial-report positive T1 forward outcome refresh.

Observed-only shadow refresh for the existing default-off SEC financial-report
positive T+1 excess-drift queue. This does not change production strategy,
thresholds, ranking, sizing, slots, exits, add-ons, LLM behavior, or universe
membership.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260511-100"
STEM = "exp_20260511_100_sec_financial_report_positive_t1_forward_outcome_refresh"
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{STEM}.json"

SOURCE_QUEUE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260510-027"
    / "sec_financial_report_non_platform_t1_queue.json"
)
SOURCE_RS20_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260510-029"
    / "sec_financial_report_rs20_slice.json"
)
SOURCE_NONPLATFORM_RS20_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260511-007"
    / "sec_nonplatform_rs20_slice.json"
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

FORWARD_HORIZONS = (1, 5, 10, 20)
SHADOW_NOTIONAL_USD = 10_000.0
ACCEPTED_CORE_METRICS = {
    "late_strong": {
        "expected_value_score": 4.2340,
        "sharpe_daily": 4.50,
        "strategy_total_return_pct": 94.09,
        "max_drawdown_pct": 5.48,
        "trade_count": 19,
        "survival_rate_pct": 80.39,
    },
    "mid_weak": {
        "expected_value_score": 1.6689,
        "sharpe_daily": 2.70,
        "strategy_total_return_pct": 61.81,
        "max_drawdown_pct": 9.41,
        "trade_count": 21,
        "survival_rate_pct": 79.25,
    },
    "old_thin": {
        "expected_value_score": 0.3853,
        "sharpe_daily": 1.35,
        "strategy_total_return_pct": 28.54,
        "max_drawdown_pct": 8.15,
        "trade_count": 22,
        "survival_rate_pct": 91.67,
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _summary(values: list[Any]) -> dict[str, Any]:
    clean = sorted(
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(float(value))
    )
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


def _as_float(row: dict[str, Any], key: str) -> float | None:
    raw = row.get(key)
    if isinstance(raw, (int, float)) and math.isfinite(float(raw)):
        return float(raw)
    return None


def _load_snapshot(snapshot_path: str) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((REPO_ROOT / snapshot_path).read_text(encoding="utf-8-sig"))
    ohlcv = payload.get("ohlcv") or {}
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        cleaned = []
        for row in rows or []:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            close = _as_float(row, "Close")
            if date_value and close is not None:
                cleaned.append({"date": date_value, "close": close})
        out[str(ticker).upper()] = sorted(cleaned, key=lambda item: item["date"])
    return out


def _index_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _forward_return(
    rows: list[dict[str, Any]],
    start_date: str,
    horizon: int,
) -> tuple[float | None, bool, str | None, str | None]:
    start_idx = _index_on_or_after(rows, start_date)
    if start_idx is None:
        return None, False, None, None
    end_idx = start_idx + horizon
    if end_idx >= len(rows):
        return None, False, rows[start_idx]["date"], None
    start_close = rows[start_idx]["close"]
    end_close = rows[end_idx]["close"]
    if start_close <= 0:
        return None, False, rows[start_idx]["date"], rows[end_idx]["date"]
    return (end_close / start_close) - 1.0, True, rows[start_idx]["date"], rows[end_idx]["date"]


def _load_source_rows() -> OrderedDict[str, list[dict[str, Any]]]:
    source = json.loads(SOURCE_QUEUE_JSON.read_text(encoding="utf-8"))
    out: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for label in WINDOWS:
        rows = []
        for row in ((source.get("windows") or {}).get(label) or {}).get("candidate_rows") or []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["window"] = label
            rows.append(item)
        out[label] = rows
    return out


def _enrich_forward(rows_by_window: OrderedDict[str, list[dict[str, Any]]]) -> OrderedDict[str, list[dict[str, Any]]]:
    enriched: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for label, rows in rows_by_window.items():
        snapshot = _load_snapshot(WINDOWS[label]["snapshot"])
        refreshed = []
        for row in rows:
            item = dict(row)
            ticker = str(item.get("ticker") or "").upper()
            ticker_rows = snapshot.get(ticker) or []
            start_date = str(item.get("shadow_entry_date") or item.get("usable_trade_date") or "")[:10]
            closed_horizons = []
            for horizon in FORWARD_HORIZONS:
                ret, closed, start_used, end_used = _forward_return(ticker_rows, start_date, horizon)
                item[f"refresh_fwd_{horizon}d_return"] = _round(ret)
                item[f"refresh_fwd_{horizon}d_pnl_proxy"] = _round(
                    ret * SHADOW_NOTIONAL_USD if ret is not None else None,
                    2,
                )
                item[f"refresh_fwd_{horizon}d_closed"] = closed
                item[f"refresh_fwd_{horizon}d_start_date"] = start_used
                item[f"refresh_fwd_{horizon}d_end_date"] = end_used
                if closed:
                    closed_horizons.append(horizon)
            item["refresh_closed_horizons"] = closed_horizons
            refreshed.append(item)
        enriched[label] = refreshed
    return enriched


def _run_core_backtest(label: str) -> dict[str, Any]:
    spec = WINDOWS[label]
    engine = BacktestEngine(
        sorted(get_universe()),
        start=spec["start"],
        end=spec["end"],
        config={
            "REGIME_AWARE_EXIT": True,
            "REPLAY_PARTIAL_REDUCES": True,
        },
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"{label} backtest failed: {result['error']}")
    return {
        "metrics": {
            "expected_value_score": _round(result.get("expected_value_score"), 4),
            "total_pnl": _round(result.get("total_pnl"), 2),
            "trade_count": int(result.get("total_trades") or 0),
            "signals_generated": int(result.get("signals_generated") or 0),
            "signals_survived": int(result.get("signals_survived") or 0),
            "survival_rate": _round(result.get("survival_rate"), 4),
            "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
            "worst_trade_pct": _round(result.get("worst_trade_pct"), 6),
            "max_consecutive_losses": int(result.get("max_consecutive_losses") or 0),
            "tail_loss_share": _round(result.get("tail_loss_share"), 4),
        },
        "trades": result.get("trades") or [],
        "entry_execution_attribution": result.get("entry_execution_attribution") or {},
    }


def _trade_key(ticker: str, date_value: str) -> tuple[str, str]:
    return (str(ticker).upper(), str(date_value)[:10])


def _overlap_summary(rows: list[dict[str, Any]], core: dict[str, Any]) -> dict[str, Any]:
    trade_keys = {
        _trade_key(trade.get("ticker"), trade.get("entry_date"))
        for trade in core.get("trades") or []
    }
    same_ticker_trade_keys = {
        str(trade.get("ticker") or "").upper()
        for trade in core.get("trades") or []
    }
    exact = []
    same_ticker = []
    non_overlap = []
    for row in rows:
        key = _trade_key(row.get("ticker"), row.get("shadow_entry_date"))
        ticker = key[0]
        if key in trade_keys:
            exact.append(row)
        elif ticker in same_ticker_trade_keys:
            same_ticker.append(row)
        else:
            non_overlap.append(row)
    return {
        "exact_entry_overlap_count": len(exact),
        "same_ticker_core_trade_count": len(same_ticker),
        "non_overlap_candidate_count": len(non_overlap),
        "exact_entry_overlap_rate": _round(len(exact) / len(rows), 4) if rows else None,
        "same_ticker_or_exact_overlap_rate": _round((len(exact) + len(same_ticker)) / len(rows), 4)
        if rows
        else None,
        "non_overlap_refresh_10d": _group_forward_summary(non_overlap, "refresh_fwd_10d_return"),
    }


def _scarce_slot_proxy(rows: list[dict[str, Any]], core: dict[str, Any]) -> dict[str, Any]:
    by_date = ((core.get("entry_execution_attribution") or {}).get("by_date") or {})
    scarce_rows = []
    slot_sliced_dates = []
    for row in rows:
        date_value = str(row.get("shadow_entry_date") or "")[:10]
        counts = by_date.get(date_value) or {}
        if int(counts.get("slot_sliced") or 0) > 0 or int(counts.get("scarce_slot_breakout_deferred") or 0) > 0:
            scarce_rows.append(row)
            slot_sliced_dates.append(date_value)
    return {
        "scarce_slot_proxy_candidate_count": len(scarce_rows),
        "scarce_slot_proxy_rate": _round(len(scarce_rows) / len(rows), 4) if rows else None,
        "dates": sorted(set(slot_sliced_dates)),
        "refresh_10d": _group_forward_summary(scarce_rows, "refresh_fwd_10d_return"),
    }


def _group_forward_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return _summary([row.get(key) for row in rows])


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "candidate_count": len(rows),
        "unique_tickers": len({str(row.get("ticker") or "").upper() for row in rows}),
        "event_family_counts": Counter(str(row.get("event_family") or "missing") for row in rows).most_common(),
        "cohort_counts": Counter(str(row.get("cohort") or "missing") for row in rows).most_common(),
        "ticker_counts": Counter(str(row.get("ticker") or "").upper() for row in rows).most_common(20),
        "closed_horizon_counts": {
            f"{horizon}d": sum(1 for row in rows if row.get(f"refresh_fwd_{horizon}d_closed"))
            for horizon in FORWARD_HORIZONS
        },
        "source_forward_returns": {
            f"fwd_{horizon}d_return": _summary([row.get(f"fwd_{horizon}d_return") for row in rows])
            for horizon in FORWARD_HORIZONS
        },
        "refreshed_forward_returns": {
            f"refresh_fwd_{horizon}d_return": _summary(
                [row.get(f"refresh_fwd_{horizon}d_return") for row in rows]
            )
            for horizon in FORWARD_HORIZONS
        },
        "refreshed_pnl_proxy": {
            f"refresh_fwd_{horizon}d_pnl_proxy": _summary(
                [row.get(f"refresh_fwd_{horizon}d_pnl_proxy") for row in rows]
            )
            for horizon in FORWARD_HORIZONS
        },
    }


def _flatten(rows_by_window: OrderedDict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for rows in rows_by_window.values() for row in rows]


def _load_prior_constraints() -> dict[str, Any]:
    constraints: dict[str, Any] = {
        "anti_repeat": [
            "Do not repeat PEAD raw reaction/volume/fixed hold retunes.",
            "Do not repeat post-news Item or surprise_direction gates.",
            "Do not promote SEC financial-report T+1 into core priority/ranking.",
            "Do not repeat platform/non-platform SEC same-sample slicing.",
            "Do not touch Space breakout/static/ETF-timing branches.",
        ],
        "source_artifacts": {},
    }
    for name, path in {
        "queue": SOURCE_QUEUE_JSON,
        "rs20": SOURCE_RS20_JSON,
        "nonplatform_rs20": SOURCE_NONPLATFORM_RS20_JSON,
    }.items():
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            constraints["source_artifacts"][name] = {
                "path": str(path.relative_to(REPO_ROOT)),
                "experiment_id": payload.get("experiment_id"),
                "decision": payload.get("decision"),
                "single_causal_variable": payload.get("single_causal_variable"),
                "rejection_reason": payload.get("rejection_reason"),
            }
    return constraints


def _build_payload() -> dict[str, Any]:
    rows_by_window = _enrich_forward(_load_source_rows())
    core_by_window = OrderedDict((label, _run_core_backtest(label)) for label in WINDOWS)

    window_payload: OrderedDict[str, Any] = OrderedDict()
    for label, rows in rows_by_window.items():
        core = core_by_window[label]
        window_payload[label] = {
            "start": WINDOWS[label]["start"],
            "end": WINDOWS[label]["end"],
            "snapshot": WINDOWS[label]["snapshot"],
            "candidate_summary": _group_summary(rows),
            "core_metrics": core["metrics"],
            "core_overlap": _overlap_summary(rows, core),
            "scarce_slot_proxy": _scarce_slot_proxy(rows, core),
            "candidate_rows": rows,
        }

    all_rows = _flatten(rows_by_window)
    positive_avg_10d_windows = sum(
        1
        for label in WINDOWS
        if (window_payload[label]["candidate_summary"]["refreshed_forward_returns"]["refresh_fwd_10d_return"]["avg"] or 0)
        > 0
    )
    positive_avg_20d_windows = sum(
        1
        for label in WINDOWS
        if (window_payload[label]["candidate_summary"]["refreshed_forward_returns"]["refresh_fwd_20d_return"]["avg"] or 0)
        > 0
    )
    total_exact_overlap = sum(
        window_payload[label]["core_overlap"]["exact_entry_overlap_count"] for label in WINDOWS
    )
    total_scarce_proxy = sum(
        window_payload[label]["scarce_slot_proxy"]["scarce_slot_proxy_candidate_count"] for label in WINDOWS
    )
    aggregate_summary = _group_summary(all_rows)
    refresh_10d = aggregate_summary["refreshed_forward_returns"]["refresh_fwd_10d_return"]
    refresh_20d = aggregate_summary["refreshed_forward_returns"]["refresh_fwd_20d_return"]

    promotion_candidate = (
        aggregate_summary["closed_horizon_counts"]["10d"] >= 100
        and positive_avg_10d_windows == 3
        and (refresh_10d["win_rate"] or 0) >= 0.52
        and (refresh_10d["avg"] or 0) > 0
        and total_exact_overlap <= 5
        and total_scarce_proxy >= 10
    )
    decision = (
        "observed_only_promotion_candidate_forward_queue"
        if promotion_candidate
        else "observed_only_no_production_promotion"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "status": "observed_only",
        "lane": "alpha_discovery",
        "decision": decision,
        "hypothesis": (
            "SEC financial-report positive T+1 drift queue may show closed forward "
            "replacement value as a default-off event interpretation surface without "
            "changing production strategy."
        ),
        "change_type": "new_strategy_shadow",
        "changed_variable": "SEC financial-report positive T1 forward outcome refresh",
        "single_causal_variable": "SEC financial-report positive T1 forward outcome refresh",
        "protocol_answers": {
            "1_alpha_hypothesis": (
                "Event interpretation / shadow candidate-pool alpha: the frozen "
                "non-platform SEC financial-report positive T+1 excess-drift queue may "
                "produce closed forward replacement value and non-overlapping scarce-slot "
                "candidates."
            ),
            "2_history_check": _load_prior_constraints(),
            "3_single_causal_variable": (
                "Refresh closed forward outcomes for the already frozen SEC queue; no "
                "new threshold, slice, ranking, sizing, or production behavior."
            ),
            "4_acceptance_standard": (
                "Observed-only. Promotion candidate requires >=100 closed 10d rows, "
                "3/3 positive 10d windows, aggregate 10d win rate >=52%, positive avg "
                "10d return, low exact core overlap, and >=10 scarce-slot proxy rows."
            ),
            "5_reproducibility": (
                "Run this Python script from the repo root. Inputs are local queue "
                "artifacts and the three docs/backtesting.md OHLCV snapshots."
            ),
        },
        "parameters": {
            "source_queue": str(SOURCE_QUEUE_JSON.relative_to(REPO_ROOT)),
            "shadow_entry": "source artifact shadow_entry_date; no new entry rule",
            "forward_horizons_trading_days": list(FORWARD_HORIZONS),
            "shadow_notional_usd": SHADOW_NOTIONAL_USD,
            "locked_variables": [
                "event family definition",
                "positive T+1 excess drift label",
                "non-platform queue definition",
                "RS20 attribution only",
                "core universe",
                "signal generation",
                "entry filters",
                "ranking",
                "sizing",
                "slots",
                "exits",
                "add-ons",
                "LLM/news replay",
            ],
        },
        "backtest_protocol": (
            "Observed-only shadow refresh using docs/backtesting.md fixed windows. "
            "Core backtests are rerun only to measure overlap/scarce-slot context; "
            "no before/after strategy behavior changed."
        ),
        "before_metrics": ACCEPTED_CORE_METRICS,
        "after_metrics": ACCEPTED_CORE_METRICS,
        "delta_metrics": {
            "aggregate": {
                "expected_value_score_delta_sum": 0.0,
                "trade_count_delta_sum": 0,
                "strategy_behavior_changed": False,
            },
            "shadow_attribution": {
                "candidate_count": aggregate_summary["candidate_count"],
                "unique_tickers": aggregate_summary["unique_tickers"],
                "closed_10d_count": aggregate_summary["closed_horizon_counts"]["10d"],
                "closed_20d_count": aggregate_summary["closed_horizon_counts"]["20d"],
                "positive_avg_10d_windows": positive_avg_10d_windows,
                "positive_avg_20d_windows": positive_avg_20d_windows,
                "refresh_10d_avg": refresh_10d["avg"],
                "refresh_10d_win_rate": refresh_10d["win_rate"],
                "refresh_20d_avg": refresh_20d["avg"],
                "refresh_20d_win_rate": refresh_20d["win_rate"],
                "exact_core_entry_overlap_count": total_exact_overlap,
                "scarce_slot_proxy_candidate_count": total_scarce_proxy,
            },
        },
        "aggregate": {
            "candidate_summary": aggregate_summary,
            "positive_avg_10d_windows": positive_avg_10d_windows,
            "positive_avg_20d_windows": positive_avg_20d_windows,
            "exact_core_entry_overlap_count": total_exact_overlap,
            "scarce_slot_proxy_candidate_count": total_scarce_proxy,
            "promotion_candidate_gate": {
                "min_closed_10d_rows": 100,
                "required_positive_avg_10d_windows": 3,
                "min_10d_win_rate": 0.52,
                "max_exact_core_overlap": 5,
                "min_scarce_slot_proxy_rows": 10,
                "passed": promotion_candidate,
            },
        },
        "windows": window_payload,
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
            "default_off_shadow_only": True,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "future_role": (
                "If forward replacement value closes positively, LLM can be tested "
                "only as a semantic financial-report quality grader, not hard risk control."
            ),
        },
        "rejection_reason": None
        if promotion_candidate
        else (
            "Observed-only refresh; evidence is not sufficient for production scope and "
            "ticket does not allow production strategy changes."
        ),
        "next_evidence_needed": [
            "Keep collecting closed forward replacement value for the frozen SEC queue.",
            "Do not retry platform/non-platform or RS20 same-sample slicing without new forward evidence.",
            "A promotion requires a separate ticket with shared default-off adapter scope and parity tests.",
        ],
        "related_files": [
            f"quant/experiments/{Path(__file__).name}",
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(SOURCE_QUEUE_JSON.relative_to(REPO_ROOT)),
            str(SOURCE_RS20_JSON.relative_to(REPO_ROOT)),
            str(SOURCE_NONPLATFORM_RS20_JSON.relative_to(REPO_ROOT)),
        ],
    }


def main() -> None:
    payload = _build_payload()
    _write_json(OUT_JSON, payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "candidate_count": payload["aggregate"]["candidate_summary"]["candidate_count"],
                "closed_10d_count": payload["delta_metrics"]["shadow_attribution"]["closed_10d_count"],
                "refresh_10d_avg": payload["delta_metrics"]["shadow_attribution"]["refresh_10d_avg"],
                "refresh_10d_win_rate": payload["delta_metrics"]["shadow_attribution"]["refresh_10d_win_rate"],
                "positive_avg_10d_windows": payload["delta_metrics"]["shadow_attribution"]["positive_avg_10d_windows"],
                "exact_core_entry_overlap_count": payload["aggregate"]["exact_core_entry_overlap_count"],
                "scarce_slot_proxy_candidate_count": payload["aggregate"]["scarce_slot_proxy_candidate_count"],
                "promotion_candidate_gate_passed": payload["aggregate"]["promotion_candidate_gate"]["passed"],
                "wrote": str(OUT_JSON.relative_to(REPO_ROOT)),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
