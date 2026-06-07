"""exp-20260606-022: accepted sleeve market-state attribution.

Observed-only alpha discovery. This script labels accepted default-off paper
sleeve replay rows with market state known before paper entry. It does not
change entries, filters, ranking, sizing, exits, reports, adapters, or orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from regime_engine import classify_market_regime  # noqa: E402
from sentiment_surface import classify_sentiment_surface  # noqa: E402


EXPERIMENT_ID = "exp-20260606-022"
STEM = "market_state_accepted_sleeve_replacement_value_attribution"
TRIAL_FAMILY = "market_state_sleeve_replacement_value_attribution"
TRIAL_VARIANT_ID = "accepted_default_off_sleeve_state_attribution_v1"
CHANGED_VARIABLE = "market_state_accepted_sleeve_replacement_value_attribution_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT_FILE = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

SOURCE_SPECS = [
    {
        "sleeve": "LOW_DEPLOYMENT_ETF_CASH_SUBSTITUTE",
        "accepted_experiment_id": "exp-20260606-001",
        "artifact": (
            "data/experiments/exp-20260606-001/"
            "exp_20260606_001_low_deployment_etf_cash_substitute_shared_adapter.json"
        ),
        "rows_key": "trades_by_window",
        "notional_note": "cash-substitute overlay rows; pnl is paper PnL versus idle cash",
    },
    {
        "sleeve": "MACRO_RELIEF_LEADERSHIP_PAPER",
        "accepted_experiment_id": "exp-20260606-020",
        "artifact": (
            "data/experiments/exp-20260606-020/"
            "exp_20260606_020_macro_relief_top2_shared_adapter.json"
        ),
        "rows_key": "target_trades_by_window",
        "notional_note": "shared adapter artifact contains full target paper rows",
    },
    {
        "sleeve": "ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER",
        "accepted_experiment_id": "exp-20260604-009",
        "artifact": (
            "data/experiments/exp-20260604-008/"
            "lagged_independent_source_consensus.json"
        ),
        "shared_artifact": (
            "data/experiments/exp-20260604-009/"
            "exp_20260604_009_lagged_consensus_shared_adapter.json"
        ),
        "rows_key": "target_trades_by_window",
        "notional_note": (
            "accepted shared adapter points to this positive replay evidence source"
        ),
    },
    {
        "sleeve": "SEC_FTD_FINRA_CONFIRMED_PAPER",
        "accepted_experiment_id": "exp-20260604-027",
        "artifact": (
            "data/experiments/exp-20260604-026/"
            "exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool.json"
        ),
        "shared_artifact": (
            "data/experiments/exp-20260604-027/"
            "exp_20260604_027_sec_ftd_finra_shared_adapter.json"
        ),
        "rows_key": "target_trades_by_window",
        "notional_note": (
            "accepted shared adapter points to this positive replay evidence source"
        ),
    },
    {
        "sleeve": "FINRA_IWM_BORROW_PRESSURE_PAPER",
        "accepted_experiment_id": "exp-20260603-007",
        "artifact": (
            "data/experiments/exp-20260603-006/"
            "exp_20260603_006_finra_borrow_pressure_candidate_pool.json"
        ),
        "shared_artifact": (
            "data/experiments/exp-20260603-007/"
            "exp_20260603_007_finra_borrow_pressure_shared_adapter.json"
        ),
        "rows_key": "target_trades_by_window",
        "notional_note": (
            "accepted shared adapter points to this positive replay evidence source"
        ),
    },
    {
        "sleeve": "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER",
        "accepted_experiment_id": "exp-20260603-022",
        "artifact": (
            "data/experiments/exp-20260603-022/"
            "exp_20260603_022_post_earnings_non_core_overlap_shared_support.json"
        ),
        "rows_key": "target_trades_by_window",
        "notional_note": "shared adapter/support artifact contains full target paper rows",
    },
]

MIN_TOTAL_ROWS_FOR_ROUTER = 120
MIN_SLEEVE_ROWS_FOR_ROUTER = 20
MIN_STATE_SLEEVE_ROWS_GLOBAL = 8
MIN_WINDOWS_WITH_STATE_SLEEVE = 2
MIN_POSITIVE_WINDOWS = 2
MIN_AVG_PNL_PCT_EDGE = 0.015
MAX_DUPLICATE_TICKER_ENTRY_SHARE = 0.25

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_state_sleeve_sample",
        "state_contrast_instability",
        "accepted_sleeve_overlap_duplicate_rows",
        "existing_state_surface_overlap",
        "no_router_justification",
    ],
    "confidence_reason": (
        "Core-only state attribution was too thin, but accepted default-off "
        "sleeve artifacts provide a wider production-visible paper outcome "
        "sample across independent mechanisms."
    ),
    "recorded_at": "2026-06-06T17:51:56+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "observed_only_no_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "diagnostic_only": True,
    "parity_note": (
        "This run only annotates already accepted default-off paper replay "
        "rows with market state known at the prior trading-day close before "
        "paper entry. A positive readout would require a separate frozen "
        "state router or sleeve allocation experiment with Gate 1-4 parity "
        "before any ranking, sizing, allocation, or order path could change."
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, set):
        return sorted(_safe(value) for value in payload)
    if isinstance(payload, Counter):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_json(path: Path | str) -> dict[str, Any]:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return json.loads(value.read_text(encoding="utf-8"))


def _load_snapshot(snapshot_path: str) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(snapshot_path)
    return payload.get("ohlcv", payload)


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    try:
        value = row.get(key)
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _series(snapshot: dict[str, list[dict[str, Any]]], ticker: str) -> list[dict[str, Any]]:
    return sorted(snapshot.get(ticker) or [], key=_date)


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows) if _date(row)}


def _trading_dates(snapshot: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [_date(row) for row in _series(snapshot, "SPY") if _date(row)]


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback or idx >= len(rows):
        return None
    start = _value(rows[idx - lookback], "Close")
    end = _value(rows[idx], "Close")
    if start is None or end is None or start <= 0:
        return None
    return (end / start) - 1.0


def _sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1 or idx >= len(rows):
        return None
    values = [_value(row, "Close") for row in rows[idx - lookback + 1 : idx + 1]]
    if any(value is None for value in values):
        return None
    clean = [float(value) for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _pct_from_sma(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    close = _value(rows[idx], "Close") if 0 <= idx < len(rows) else None
    avg = _sma(rows, idx, lookback)
    if close is None or avg is None or avg <= 0:
        return None
    return (close / avg) - 1.0


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


def _bucket_market_context(context: dict[str, Any]) -> dict[str, str]:
    spy20 = context.get("spy_20d_return")
    qqq20 = context.get("qqq_20d_return")
    spy10 = context.get("spy_10d_return")
    qqq10 = context.get("qqq_10d_return")
    spy_pct = context.get("spy_pct_from_ma")
    qqq_pct = context.get("qqq_pct_from_ma")
    qqq_rel = context.get("qqq_minus_spy_ret20")

    broad_up = (
        spy20 is not None
        and qqq20 is not None
        and spy20 > 0.03
        and qqq20 > 0.04
        and (spy_pct is None or spy_pct > 0.0)
        and (qqq_pct is None or qqq_pct > 0.0)
    )
    broad_down = (
        (spy20 is not None and spy20 < -0.03)
        or (qqq20 is not None and qqq20 < -0.04)
        or (spy_pct is not None and spy_pct < -0.02)
        or (qqq_pct is not None and qqq_pct < -0.02)
    )
    if broad_up:
        trend_pressure = "broad_up"
    elif broad_down:
        trend_pressure = "broad_down"
    else:
        trend_pressure = "mixed"

    if qqq_rel is None:
        growth_leadership = "unknown"
    elif qqq_rel >= 0.03:
        growth_leadership = "qqq_leads"
    elif qqq_rel <= -0.015:
        growth_leadership = "spy_defensive_leads"
    else:
        growth_leadership = "balanced"

    max_10 = max([value for value in [spy10, qqq10] if value is not None], default=None)
    max_20 = max([value for value in [spy20, qqq20] if value is not None], default=None)
    min_10 = min([value for value in [spy10, qqq10] if value is not None], default=None)
    if (max_10 is not None and max_10 >= 0.05) or (max_20 is not None and max_20 >= 0.08):
        extension = "extended"
    elif min_10 is not None and min_10 <= -0.03:
        extension = "pullback"
    else:
        extension = "normal"

    return {
        "trend_pressure": trend_pressure,
        "growth_leadership": growth_leadership,
        "extension": extension,
        "combined_state": f"{trend_pressure}|{growth_leadership}|{extension}",
    }


def _state_for_entry_date(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    trading_dates: list[str],
    entry_date: str,
) -> dict[str, Any] | None:
    date_pos = {value: idx for idx, value in enumerate(trading_dates)}
    entry_pos = date_pos.get(entry_date)
    if entry_pos is None or entry_pos < 1:
        return None
    state_date = trading_dates[entry_pos - 1]
    spy_rows = _series(snapshot, "SPY")
    qqq_rows = _series(snapshot, "QQQ")
    spy_idx = _row_index(spy_rows).get(state_date)
    qqq_idx = _row_index(qqq_rows).get(state_date)
    if spy_idx is None or qqq_idx is None:
        return None

    context = {
        "spy_pct_from_ma": _pct_from_sma(spy_rows, spy_idx, 200),
        "qqq_pct_from_ma": _pct_from_sma(qqq_rows, qqq_idx, 200),
        "spy_10d_return": _ret(spy_rows, spy_idx, 10),
        "qqq_10d_return": _ret(qqq_rows, qqq_idx, 10),
        "spy_20d_return": _ret(spy_rows, spy_idx, 20),
        "qqq_20d_return": _ret(qqq_rows, qqq_idx, 20),
        "theme_signal_count": 0,
        "breakout_signal_count": 0,
        "ai_signal_count": 0,
        "crypto_signal_count": 0,
        "space_signal_count": 0,
    }
    if context["qqq_20d_return"] is not None and context["spy_20d_return"] is not None:
        context["qqq_minus_spy_ret20"] = (
            float(context["qqq_20d_return"]) - float(context["spy_20d_return"])
        )
    else:
        context["qqq_minus_spy_ret20"] = None

    regime = classify_market_regime(context)
    sentiment = classify_sentiment_surface(context)
    buckets = _bucket_market_context(context)
    return {
        "state_date": state_date,
        "state_known_at": "prior_trading_day_close_before_entry_open",
        "regime": regime.get("regime"),
        "regime_confidence": regime.get("confidence"),
        "sentiment": sentiment.get("sentiment"),
        "sentiment_confidence": sentiment.get("confidence"),
        "sentiment_why": sentiment.get("why") or [],
        **buckets,
        "features": {
            key: _round(value)
            for key, value in context.items()
            if key
            in {
                "spy_pct_from_ma",
                "qqq_pct_from_ma",
                "spy_10d_return",
                "qqq_10d_return",
                "spy_20d_return",
                "qqq_20d_return",
                "qqq_minus_spy_ret20",
            }
        },
    }


def _baseline_summary() -> dict[str, Any]:
    payload = _load_json(BASELINE_RESULT_FILE)
    windows = payload.get("windows") or []
    return {
        "baseline_result_file": _repo_rel(BASELINE_RESULT_FILE),
        "windows": windows,
        "aggregate": {
            "expected_value_score_sum": _round(
                sum(float(row.get("expected_value_score") or 0.0) for row in windows),
                4,
            ),
            "total_pnl_sum": _round(
                sum(float(row.get("total_pnl") or 0.0) for row in windows),
                2,
            ),
            "trade_count_sum": int(sum(int(row.get("trade_count") or 0) for row in windows)),
            "min_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in windows),
                6,
            )
            if windows
            else None,
            "max_drawdown_pct_max": _round(
                max(float(row.get("max_drawdown_pct") or 0.0) for row in windows),
                4,
            )
            if windows
            else None,
        },
    }


def _pnl_pct(row: dict[str, Any]) -> float | None:
    value = _round(row.get("pnl_pct_net"), 10)
    if value is not None:
        return value
    pnl = _round(row.get("pnl"), 10)
    notional = _round(row.get("paper_notional_usd"), 10)
    if pnl is None or notional is None or notional <= 0:
        return None
    return pnl / notional


def _normalize_row(
    *,
    spec: dict[str, Any],
    window: str,
    row: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper()
    entry_date = str(row.get("entry_date") or "")[:10]
    pnl = _round(row.get("pnl"), 2)
    notional = _round(row.get("paper_notional_usd"), 2)
    pnl_pct = _pnl_pct(row)
    if not ticker or not entry_date or pnl is None or notional is None or notional <= 0:
        return None
    return {
        "sleeve": spec["sleeve"],
        "accepted_experiment_id": spec["accepted_experiment_id"],
        "source_artifact": spec["artifact"],
        "window": window,
        "ticker": ticker,
        "signal_date": str(row.get("signal_date") or row.get("date") or "")[:10],
        "entry_date": entry_date,
        "exit_date": str(row.get("exit_date") or "")[:10],
        "paper_notional_usd": notional,
        "pnl": pnl,
        "pnl_pct_net": _round(pnl_pct, 6),
        "pnl_per_10k": _round((pnl_pct or 0.0) * 10_000.0, 2),
        "win": bool(pnl > 0),
        "strategy": row.get("strategy") or row.get("source") or spec["sleeve"],
        "decision_id": row.get("decision_id"),
        "trade_enabled": bool(row.get("trade_enabled") is True),
        "alters_orders": bool(row.get("alters_orders") is True),
        "row_fingerprint": (
            f"{spec['sleeve']}|{window}|{ticker}|{entry_date}|"
            f"{str(row.get('exit_date') or '')[:10]}|{pnl}"
        ),
        **state,
    }


def _extract_source_rows(
    spec: dict[str, Any],
    snapshots: dict[str, dict[str, list[dict[str, Any]]]],
    trading_dates_by_window: dict[str, list[str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = REPO_ROOT / str(spec["artifact"])
    source_report = {
        "sleeve": spec["sleeve"],
        "accepted_experiment_id": spec["accepted_experiment_id"],
        "artifact": spec["artifact"],
        "shared_artifact": spec.get("shared_artifact"),
        "artifact_exists": path.exists(),
        "rows_total": 0,
        "rows_with_required_fields": 0,
        "rows_with_state": 0,
        "missing_state_rows": 0,
        "invalid_rows": 0,
        "windows": {},
        "notional_note": spec["notional_note"],
    }
    if not path.exists():
        source_report["blocker"] = "artifact_missing"
        return [], source_report

    payload = _load_json(path)
    by_window = payload.get(spec["rows_key"]) or {}
    if not isinstance(by_window, dict):
        source_report["blocker"] = "rows_key_missing_or_not_dict"
        return [], source_report

    rows: list[dict[str, Any]] = []
    for window, cfg in WINDOWS.items():
        source_rows = by_window.get(window) or []
        if not isinstance(source_rows, list):
            source_rows = []
        extracted = 0
        missing_state = 0
        invalid_rows = 0
        for raw in source_rows:
            if not isinstance(raw, dict):
                invalid_rows += 1
                continue
            source_report["rows_total"] += 1
            if raw.get("entry_date") and raw.get("ticker") and raw.get("pnl") is not None:
                source_report["rows_with_required_fields"] += 1
            entry_date = str(raw.get("entry_date") or "")[:10]
            state = _state_for_entry_date(
                snapshot=snapshots[window],
                trading_dates=trading_dates_by_window[window],
                entry_date=entry_date,
            )
            if state is None:
                missing_state += 1
                continue
            normalized = _normalize_row(spec=spec, window=window, row=raw, state=state)
            if normalized is None:
                invalid_rows += 1
                continue
            rows.append(normalized)
            extracted += 1
        source_report["windows"][window] = {
            "input_rows": len(source_rows),
            "rows_with_state": extracted,
            "missing_state_rows": missing_state,
            "invalid_rows": invalid_rows,
            "window_start": cfg["start"],
            "window_end": cfg["end"],
        }
        source_report["rows_with_state"] += extracted
        source_report["missing_state_rows"] += missing_state
        source_report["invalid_rows"] += invalid_rows
    return rows, source_report


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [float(row["pnl"]) for row in rows if row.get("pnl") is not None]
    pct_values = [
        float(row["pnl_pct_net"])
        for row in rows
        if row.get("pnl_pct_net") is not None
    ]
    per_10k = [
        float(row["pnl_per_10k"])
        for row in rows
        if row.get("pnl_per_10k") is not None
    ]
    tickers = Counter(str(row.get("ticker") or "") for row in rows)
    windows = Counter(str(row.get("window") or "") for row in rows)
    states = Counter(str(row.get("combined_state") or "") for row in rows)
    if not pnl_values:
        return {
            "trades": 0,
            "win_rate": None,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "median_pnl": None,
            "avg_pnl_pct": None,
            "median_pnl_pct": None,
            "avg_pnl_per_10k": None,
            "median_pnl_per_10k": None,
            "worst_pnl_pct": None,
            "best_pnl_pct": None,
            "unique_tickers": 0,
        }
    return {
        "trades": len(pnl_values),
        "win_rate": _round(sum(1 for value in pnl_values if value > 0) / len(pnl_values), 4),
        "total_pnl": _round(sum(pnl_values), 2),
        "avg_pnl": _round(mean(pnl_values), 2),
        "median_pnl": _round(median(pnl_values), 2),
        "avg_pnl_pct": _round(mean(pct_values), 6) if pct_values else None,
        "median_pnl_pct": _round(median(pct_values), 6) if pct_values else None,
        "avg_pnl_per_10k": _round(mean(per_10k), 2) if per_10k else None,
        "median_pnl_per_10k": _round(median(per_10k), 2) if per_10k else None,
        "worst_pnl_pct": _round(min(pct_values), 6) if pct_values else None,
        "best_pnl_pct": _round(max(pct_values), 6) if pct_values else None,
        "unique_tickers": len([ticker for ticker in tickers if ticker]),
        "top_tickers": tickers.most_common(8),
        "windows": dict(sorted(windows.items())),
        "states": dict(sorted(states.items())),
    }


def _group_summary(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = "|".join(str(row.get(part) or "unknown") for part in keys)
        grouped[key].append(row)
    return {
        key: _summarize_rows(value)
        for key, value in sorted(grouped.items(), key=lambda item: item[0])
    }


def _overlap_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("window") or ""),
            str(row.get("ticker") or ""),
            str(row.get("entry_date") or ""),
            str(row.get("exit_date") or ""),
        )
        grouped[key].append(row)
    duplicate_groups = []
    duplicate_rows = 0
    for key, value in grouped.items():
        sleeves = sorted({str(row.get("sleeve") or "") for row in value})
        if len(value) <= 1 or len(sleeves) <= 1:
            continue
        duplicate_rows += len(value)
        duplicate_groups.append(
            {
                "window": key[0],
                "ticker": key[1],
                "entry_date": key[2],
                "exit_date": key[3],
                "row_count": len(value),
                "sleeves": sleeves,
                "total_pnl": _round(sum(float(row.get("pnl") or 0.0) for row in value), 2),
            }
        )
    duplicate_groups.sort(
        key=lambda row: (-int(row["row_count"]), row["window"], row["ticker"], row["entry_date"])
    )
    return {
        "duplicate_ticker_entry_groups": len(duplicate_groups),
        "duplicate_rows": duplicate_rows,
        "duplicate_row_share": _round(duplicate_rows / len(rows), 6) if rows else 0.0,
        "max_allowed_duplicate_row_share_for_router": MAX_DUPLICATE_TICKER_ENTRY_SHARE,
        "sample_duplicate_groups": duplicate_groups[:20],
    }


def _router_readiness(rows: list[dict[str, Any]], overlap: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    total_rows = len(rows)
    sleeve_counts = Counter(str(row.get("sleeve") or "") for row in rows)
    state_counts = Counter(str(row.get("combined_state") or "") for row in rows)
    sleeve_state_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        sleeve_state_counts[str(row.get("sleeve") or "")][str(row.get("combined_state") or "")] += 1

    if total_rows < MIN_TOTAL_ROWS_FOR_ROUTER:
        failed.append("total_state_labeled_rows_below_router_floor")
    sleeves_with_enough_rows = [
        sleeve
        for sleeve, count in sleeve_counts.items()
        if count >= MIN_SLEEVE_ROWS_FOR_ROUTER
    ]
    if len(sleeves_with_enough_rows) < 3:
        failed.append("too_few_sleeves_with_router_grade_sample")
    if float(overlap.get("duplicate_row_share") or 0.0) > MAX_DUPLICATE_TICKER_ENTRY_SHARE:
        failed.append("accepted_sleeve_overlap_duplicate_rows")

    global_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    window_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (str(row.get("sleeve") or ""), str(row.get("combined_state") or ""))
        global_groups[key].append(row)
        window_groups[(str(row.get("window") or ""), *key)].append(row)

    candidates: list[dict[str, Any]] = []
    for (sleeve, state), group_rows in sorted(global_groups.items()):
        if len(group_rows) < MIN_STATE_SLEEVE_ROWS_GLOBAL:
            continue
        comparator_rows = [
            row
            for row in rows
            if row.get("sleeve") == sleeve and row.get("combined_state") != state
        ]
        if len(comparator_rows) < MIN_STATE_SLEEVE_ROWS_GLOBAL:
            continue
        group_summary = _summarize_rows(group_rows)
        comparator_summary = _summarize_rows(comparator_rows)
        group_avg = group_summary.get("avg_pnl_pct")
        comparator_avg = comparator_summary.get("avg_pnl_pct")
        if group_avg is None or comparator_avg is None:
            continue
        edge = float(group_avg) - float(comparator_avg)
        window_summaries = {
            window: _summarize_rows(window_rows)
            for (window, group_sleeve, group_state), window_rows in window_groups.items()
            if group_sleeve == sleeve and group_state == state
        }
        windows_with_sample = sum(
            1 for summary in window_summaries.values() if summary.get("trades", 0) > 0
        )
        positive_windows = sum(
            1
            for summary in window_summaries.values()
            if summary.get("avg_pnl_pct") is not None
            and float(summary["avg_pnl_pct"]) > 0
        )
        if (
            float(group_avg) > 0
            and edge >= MIN_AVG_PNL_PCT_EDGE
            and windows_with_sample >= MIN_WINDOWS_WITH_STATE_SLEEVE
            and positive_windows >= MIN_POSITIVE_WINDOWS
        ):
            candidates.append(
                {
                    "sleeve": sleeve,
                    "combined_state": state,
                    "global": group_summary,
                    "same_sleeve_other_states": comparator_summary,
                    "edge_vs_same_sleeve_other_states_avg_pnl_pct": _round(edge, 6),
                    "windows_with_sample": windows_with_sample,
                    "positive_windows": positive_windows,
                    "window_summaries": window_summaries,
                }
            )
    candidates.sort(
        key=lambda row: (
            -float(row.get("edge_vs_same_sleeve_other_states_avg_pnl_pct") or 0.0),
            -int(row.get("global", {}).get("trades") or 0),
            row.get("sleeve") or "",
            row.get("combined_state") or "",
        )
    )
    if not candidates:
        failed.append("no_stable_positive_state_sleeve_candidate")

    ready = not failed
    return {
        "ready_for_router_gate": ready,
        "decision": (
            "observed_only_router_candidate_requires_separate_gate_1_4"
            if ready
            else "observed_only_no_router_yet_state_sleeve_edge_unstable_or_overlapped"
        ),
        "failed_reasons": failed,
        "thresholds": {
            "min_total_rows_for_router": MIN_TOTAL_ROWS_FOR_ROUTER,
            "min_sleeve_rows_for_router": MIN_SLEEVE_ROWS_FOR_ROUTER,
            "min_state_sleeve_rows_global": MIN_STATE_SLEEVE_ROWS_GLOBAL,
            "min_windows_with_state_sleeve": MIN_WINDOWS_WITH_STATE_SLEEVE,
            "min_positive_windows": MIN_POSITIVE_WINDOWS,
            "min_avg_pnl_pct_edge": MIN_AVG_PNL_PCT_EDGE,
            "max_duplicate_ticker_entry_share": MAX_DUPLICATE_TICKER_ENTRY_SHARE,
        },
        "total_rows": total_rows,
        "sleeve_counts": dict(sorted(sleeve_counts.items())),
        "state_counts": dict(sorted(state_counts.items())),
        "sleeve_state_counts": {
            sleeve: dict(sorted(counts.items()))
            for sleeve, counts in sorted(sleeve_state_counts.items())
        },
        "sleeves_with_router_grade_sample": sleeves_with_enough_rows,
        "candidate_count": len(candidates),
        "top_candidates": candidates[:12],
    }


def _field_reality(source_reports: list[dict[str, Any]]) -> dict[str, Any]:
    total_rows = sum(int(row.get("rows_total") or 0) for row in source_reports)
    required = sum(int(row.get("rows_with_required_fields") or 0) for row in source_reports)
    state = sum(int(row.get("rows_with_state") or 0) for row in source_reports)
    return {
        "required_source_fields": [
            "target/trade row entry_date",
            "target/trade row ticker",
            "target/trade row pnl",
            "target/trade row paper_notional_usd",
        ],
        "operator_position_fields_required_for_this_read_only_run": False,
        "source_rows_total": total_rows,
        "source_rows_with_required_fields": required,
        "source_required_field_coverage": _round(required / total_rows, 6)
        if total_rows
        else None,
        "source_rows_with_market_state": state,
        "market_state_coverage": _round(state / total_rows, 6) if total_rows else None,
        "blocked": required != total_rows or state == 0,
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    baseline = _baseline_summary()
    snapshots = {
        label: _load_snapshot(cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }
    trading_dates_by_window = {
        label: _trading_dates(snapshot)
        for label, snapshot in snapshots.items()
    }

    all_rows: list[dict[str, Any]] = []
    source_reports: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        print(f"[{spec['sleeve']}] extracting accepted paper rows")
        rows, report = _extract_source_rows(spec, snapshots, trading_dates_by_window)
        all_rows.extend(rows)
        source_reports.append(report)
        print(
            f"  rows={report['rows_total']} state={report['rows_with_state']} "
            f"artifact={spec['artifact']}"
        )

    overlap = _overlap_diagnostics(all_rows)
    readiness = _router_readiness(all_rows, overlap)
    decision = readiness["decision"]
    status = "observed_only"
    field_reality = _field_reality(source_reports)

    if readiness["ready_for_router_gate"]:
        interpretation = (
            "Observed-only attribution found at least one sleeve/state cell "
            "with enough sample, positive normalized PnL, and a stable edge "
            "versus the same sleeve in other states. This is not an accepted "
            "strategy change; it only justifies a separate frozen Gate 1-4 "
            "router experiment."
        )
    else:
        interpretation = (
            "Observed-only attribution does not justify a state-conditioned "
            "accepted-sleeve router. The labeled sample is useful, but the "
            "state-sleeve edge is unstable, too overlapped, or lacks a robust "
            "positive candidate under the preregistered thresholds."
        )

    windows_summary = {
        window: {
            "start": WINDOWS[window]["start"],
            "end": WINDOWS[window]["end"],
            "snapshot": WINDOWS[window]["snapshot"],
            "rows": len([row for row in all_rows if row["window"] == window]),
            "summary_by_sleeve": _group_summary(
                [row for row in all_rows if row["window"] == window],
                ["sleeve"],
            ),
            "summary_by_combined_state": _group_summary(
                [row for row in all_rows if row["window"] == window],
                ["combined_state"],
            ),
            "summary_by_sleeve_and_state": _group_summary(
                [row for row in all_rows if row["window"] == window],
                ["sleeve", "combined_state"],
            ),
            "sample_rows": [row for row in all_rows if row["window"] == window][:40],
        }
        for window in WINDOWS
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_discovery",
        "status": status,
        "decision": decision,
        "accepted": False,
        "diagnostic_only": True,
        "hypothesis": (
            "Accepted default-off paper sleeve outcomes may show stable "
            "market-state-by-sleeve replacement value, enabling a later "
            "frozen state-conditioned sleeve router without touching live "
            "orders in this run."
        ),
        "change_type": "read_only_market_state_accepted_sleeve_attribution",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "read_only_market_state_accepted_sleeve_attribution",
        "new_evidence_type": "accepted_default_off_sleeve_state_replacement_value_attribution",
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260606-021",
            "exp-20260606-001",
            "exp-20260606-020",
            "exp-20260604-009",
            "exp-20260604-027",
            "exp-20260603-007",
            "exp-20260603-022",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "prediction": PREDICTION,
        "production_impact": PRODUCTION_IMPACT,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three fixed windows plus "
                "read-only accepted default-off paper sleeve replay artifacts"
            ),
            "baseline_result_file": _repo_rel(BASELINE_RESULT_FILE),
            "windows": WINDOWS,
            "state_timing": "prior_trading_day_close_before_entry_open",
            "execution_impact": "none_observed_only_attribution",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/risk allocation precursor: accepted default-off "
                "paper sleeves may have state-conditioned normalized PnL "
                "that can guide a later router."
            ),
            "2_history_check": (
                "exp-20260606-021 found core-only state-family attribution "
                "too thin. This run uses accepted sleeve rows from "
                "exp-20260606-001, exp-20260606-020, exp-20260604-009, "
                "exp-20260604-027, exp-20260603-007, and exp-20260603-022."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: no production alpha can be accepted here. "
                "A positive result requires enough state-labeled rows, a "
                "stable same-sleeve normalized PnL edge across at least two "
                "windows, and acceptable duplicate-overlap diagnostics before "
                "opening a separate Gate 1-4 router experiment."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260606_022_market_state_accepted_sleeve_replacement_value_attribution.py"
            ),
        },
        "gate1_baseline": baseline,
        "gate2_field_reality": field_reality,
        "gate3_survival_audit": {
            "min_core_survival_rate": baseline["aggregate"]["min_survival_rate"],
            "adds_filter": False,
            "survival_guard_passed": (
                baseline["aggregate"]["min_survival_rate"] is not None
                and baseline["aggregate"]["min_survival_rate"] >= 0.05
            ),
        },
        "gate4_observed_only": {
            "changes_strategy_behavior": False,
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "accepted_strategy_change": False,
            "decision": decision,
            "failed_reasons": readiness["failed_reasons"],
        },
        "source_reports": source_reports,
        "source_evidence_quality": {
            "uses_forward_live_closed_rows": False,
            "uses_historical_accepted_replay_rows": True,
            "normalization": "pnl_pct_net and pnl_per_10k; raw PnL is not comparable across sleeves",
            "replacement_value_caveat": (
                "Rows are accepted historical paper replay outcomes. They are "
                "not sufficient activation evidence and do not replace closed "
                "forward replacement-value rows."
            ),
        },
        "row_count": len(all_rows),
        "overlap_diagnostics": overlap,
        "aggregate_summary_by_sleeve": _group_summary(all_rows, ["sleeve"]),
        "aggregate_summary_by_combined_state": _group_summary(all_rows, ["combined_state"]),
        "aggregate_summary_by_sleeve_and_state": _group_summary(
            all_rows, ["sleeve", "combined_state"]
        ),
        "windows": windows_summary,
        "router_readiness": readiness,
        "interpretation": interpretation,
        "negative_reflection": (
            "If rejected, the reason is not that market state is useless. It "
            "means accepted sleeve samples are still too overlapped or "
            "state-unstable to justify a router. The next valid step is "
            "closed forward replacement-value rows or a less overlapping "
            "sleeve-displacement audit, not retuning accepted sleeve thresholds."
        ),
        "next_experiment_hint": (
            "Use forward closed replacement-value rows for the same accepted "
            "sleeves, or compute exact displacement among overlapping sleeves, "
            "before testing any state-conditioned allocation router."
        ),
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_discovery",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "diagnostic_only": True,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["backtest_protocol"]["baseline_result_file"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "row_count": payload["row_count"],
        "source_reports": payload["source_reports"],
        "overlap_diagnostics": payload["overlap_diagnostics"],
        "router_readiness": payload["router_readiness"],
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": None,
            "actual_observed_readiness_passed": payload["router_readiness"][
                "ready_for_router_gate"
            ],
            "failure_modes_observed": payload["router_readiness"]["failed_reasons"],
            "brier_score": _round(
                (
                    (1.0 if payload["router_readiness"]["ready_for_router_gate"] else 0.0)
                    - float(PREDICTION["success_probability"])
                )
                ** 2,
                6,
            ),
            "calibration_direction": (
                "underconfident"
                if payload["router_readiness"]["ready_for_router_gate"]
                and float(PREDICTION["success_probability"]) < 0.5
                else "directionally_calibrated"
            ),
        },
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    source_rows = [
        "| Sleeve | Rows | State Rows | Artifact |",
        "|---|---:|---:|---|",
    ]
    for report in payload["source_reports"]:
        source_rows.append(
            "| {sleeve} | {rows} | {state} | `{artifact}` |".format(
                sleeve=report["sleeve"],
                rows=int(report.get("rows_total") or 0),
                state=int(report.get("rows_with_state") or 0),
                artifact=report["artifact"],
            )
        )

    top_candidates = payload["router_readiness"]["top_candidates"][:5]
    candidate_rows = [
        "| Sleeve | State | Trades | Avg PnL % | Edge vs Other States | Windows + |",
        "|---|---|---:|---:|---:|---:|",
    ]
    if top_candidates:
        for row in top_candidates:
            candidate_rows.append(
                "| {sleeve} | {state} | {trades} | {avg:.2%} | {edge:.2%} | {pos}/{sample} |".format(
                    sleeve=row["sleeve"],
                    state=str(row["combined_state"]).replace("|", "/"),
                    trades=int(row["global"].get("trades") or 0),
                    avg=float(row["global"].get("avg_pnl_pct") or 0.0),
                    edge=float(row.get("edge_vs_same_sleeve_other_states_avg_pnl_pct") or 0.0),
                    pos=int(row.get("positive_windows") or 0),
                    sample=int(row.get("windows_with_sample") or 0),
                )
            )
    else:
        candidate_rows.append("| n/a | n/a | 0 | 0.00% | 0.00% | 0/0 |")

    readiness = payload["router_readiness"]
    overlap = payload["overlap_diagnostics"]
    return "\n".join(
        [
            f"---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            f'lane: "alpha_discovery"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            f"---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            "## Summary",
            "",
            payload["hypothesis"],
            "",
            "## Source Coverage",
            "",
            *source_rows,
            "",
            "## Router Readiness",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Ready for separate router Gate 1-4: `{readiness['ready_for_router_gate']}`",
            f"- Failed reasons: `{', '.join(readiness['failed_reasons']) or 'none'}`",
            f"- State-labeled rows: `{readiness['total_rows']}`",
            f"- Duplicate ticker-entry row share: `{overlap['duplicate_row_share']}`",
            "",
            "## Top State/Sleeve Cells",
            "",
            *candidate_rows,
            "",
            "## Conclusion",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            (
                "Observed-only. No shared policy, run adapter, backtester adapter, "
                "watchlist, order path, core entry, ranking, sizing, allocation, "
                "or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "accepted": False,
                "diagnostic_only": True,
                "aggregate_expected_value_delta": 0.0,
                "aggregate_strategy_total_pnl_delta": 0.0,
                "row_count": payload["row_count"],
                "router_readiness": payload["router_readiness"],
                "overlap_diagnostics": payload["overlap_diagnostics"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    registry = _load_json(REGISTRY_JSON) if REGISTRY_JSON.exists() else {
        "schema_version": 1,
        "experiments": [],
    }
    experiments = registry.setdefault("experiments", [])
    found = False
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": 0.0,
                "aggregate_strategy_total_pnl_delta": 0.0,
            }
        )
        found = True
        break
    if not found:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": "alpha_discovery",
                "owner": "alpha-search",
                "hypothesis": payload["hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "card_file": _repo_rel(CARD_MD),
                "revision_manifest_file": _repo_rel(MANIFEST_JSON),
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "updated_at": payload["timestamp"],
            }
        )
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(_safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "manifest_type": "ginger_experiment_revision_manifest",
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "files": {
            _repo_rel(Path(__file__)): {"exists": Path(__file__).exists(), "sha256": _sha256(Path(__file__))},
            _repo_rel(OUT_JSON): {"exists": OUT_JSON.exists(), "sha256": _sha256(OUT_JSON)},
            _repo_rel(LOG_JSON): {"exists": LOG_JSON.exists(), "sha256": _sha256(LOG_JSON)},
            _repo_rel(TICKET_JSON): {"exists": TICKET_JSON.exists(), "sha256": _sha256(TICKET_JSON)},
            _repo_rel(CARD_MD): {"exists": CARD_MD.exists(), "sha256": _sha256(CARD_MD)},
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
