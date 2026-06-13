"""exp-20260606-021: market-state family replacement-value attribution.

Observed-only alpha discovery. This script tests whether market state known
before trade entry explains realized outcomes by strategy family. It does not
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
for import_path in (QUANT_DIR,):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from regime_engine import classify_market_regime  # noqa: E402
from sentiment_surface import classify_sentiment_surface  # noqa: E402


EXPERIMENT_ID = "exp-20260606-021"
STEM = "market_state_family_replacement_value_attribution"
TRIAL_FAMILY = "market_state_family_replacement_value_attribution"
TRIAL_VARIANT_ID = "observed_only_core_trade_state_family_attribution_v1"
CHANGED_VARIABLE = "market_state_strategy_family_attribution_v1"

# exp-20260612-017: warehouse relocated to data/warehouse/; resolve via module.
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH as WAREHOUSE  # noqa: E402
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_021_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
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

MIN_TOTAL_TRADES_FOR_ROUTER = 60
MIN_FAMILY_TRADES_FOR_ROUTER = 15
MIN_STATE_FAMILY_TRADES_GLOBAL = 6
MIN_WINDOWS_WITH_STATE_FAMILY = 2
MIN_STATE_FAMILY_R_EDGE = 0.25

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_monotonic_state_edge",
        "thin_family_state_sample",
        "window_instability",
        "existing_state_surface_overlap",
        "no_router_justification",
    ],
    "confidence_reason": (
        "Market-state analysis is diagnostic-only today, but recent broad "
        "continuation and tail-state failures suggest family-level realized "
        "value may cluster by state more usefully than another threshold "
        "retune."
    ),
    "recorded_at": "2026-06-06T17:21:24Z",
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
        "This run only annotates already-closed canonical core trades with "
        "market state known at the prior trading-day close before entry. A "
        "positive result would require a separate frozen shared router or "
        "paper adapter with Gate 1-4 production/backtest parity before any "
        "allocation or ranking behavior could change."
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


def _load_snapshot(snapshot_path: str) -> dict[str, list[dict[str, Any]]]:
    path = REPO_ROOT / snapshot_path
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("ohlcv", payload)


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    try:
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
    if not clean:
        return None
    return sum(clean) / len(clean)


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


def _r_multiple(trade: dict[str, Any]) -> float | None:
    entry = _round(trade.get("entry_price"), 10)
    stop = _round(trade.get("stop_price"), 10)
    shares = _round(trade.get("shares"), 10)
    pnl = _round(trade.get("pnl"), 10)
    if pnl is None:
        pnl = _round(trade.get("profit_loss"), 10)
    if entry is None or stop is None or shares is None or pnl is None:
        return None
    if entry <= stop or shares <= 0:
        return None
    risk = (entry - stop) * shares
    if risk <= 0:
        return None
    return pnl / risk


def _metrics(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("expected_value_score") is None:
        result["expected_value_score"] = compute_expected_value_score(result)
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "strategy_total_return_pct": _round(
            result.get("benchmarks", {}).get("strategy_total_return_pct"), 4
        ),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "trade_count": int(result.get("total_trades") or len(result.get("trades") or [])),
        "win_rate": _round(result.get("win_rate"), 4),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(result.get("survival_rate"), 6),
    }


def _run_baseline(universe: list[str], cfg: dict[str, str]) -> dict[str, Any]:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_warehouse_path=str(WAREHOUSE),
        ohlcv_warehouse_snapshot_source=cfg["snapshot"],
    )
    result = engine.run()
    if result.get("error"):
        raise RuntimeError(f"baseline failed for {cfg}: {result['error']}")
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [_round(row.get("pnl"), 10) for row in rows]
    pnl_values = [float(value) for value in pnl_values if value is not None]
    r_values = [_round(row.get("r_multiple"), 10) for row in rows]
    r_values = [float(value) for value in r_values if value is not None]
    tickers = Counter(str(row.get("ticker") or "") for row in rows)
    windows = Counter(str(row.get("window") or "") for row in rows)
    strategies = Counter(str(row.get("strategy_family") or "") for row in rows)
    if not pnl_values:
        return {
            "trades": 0,
            "win_rate": None,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "median_pnl": None,
            "avg_r": None,
            "median_r": None,
            "worst_trade": None,
            "best_trade": None,
            "unique_tickers": 0,
            "windows": {},
            "strategies": {},
        }
    return {
        "trades": len(pnl_values),
        "win_rate": _round(sum(1 for value in pnl_values if value > 0) / len(pnl_values), 4),
        "total_pnl": _round(sum(pnl_values), 2),
        "avg_pnl": _round(mean(pnl_values), 2),
        "median_pnl": _round(median(pnl_values), 2),
        "avg_r": _round(mean(r_values), 4) if r_values else None,
        "median_r": _round(median(r_values), 4) if r_values else None,
        "worst_trade": _round(min(pnl_values), 2),
        "best_trade": _round(max(pnl_values), 2),
        "unique_tickers": len([ticker for ticker in tickers if ticker]),
        "top_tickers": tickers.most_common(8),
        "windows": dict(sorted(windows.items())),
        "strategies": dict(sorted(strategies.items())),
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


def _extract_window_rows(
    *,
    label: str,
    cfg: dict[str, str],
    result: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trading_dates = _trading_dates(snapshot)
    rows: list[dict[str, Any]] = []
    missing_state = 0
    for trade in result.get("trades") or []:
        entry_date = str(trade.get("entry_date") or "")[:10]
        state = _state_for_entry_date(
            snapshot=snapshot,
            trading_dates=trading_dates,
            entry_date=entry_date,
        )
        if state is None:
            missing_state += 1
            continue
        pnl = _round(trade.get("pnl"), 10)
        if pnl is None:
            pnl = _round(trade.get("profit_loss"), 10)
        rows.append(
            {
                "window": label,
                "window_start": cfg["start"],
                "window_end": cfg["end"],
                "ticker": str(trade.get("ticker") or "").upper(),
                "sector": trade.get("sector"),
                "strategy_family": str(trade.get("strategy") or "unknown"),
                "entry_date": entry_date,
                "exit_date": str(trade.get("exit_date") or "")[:10],
                "entry_price": _round(trade.get("entry_price"), 4),
                "exit_price": _round(trade.get("exit_price"), 4),
                "stop_price": _round(trade.get("stop_price"), 4),
                "shares": _round(trade.get("shares"), 4),
                "pnl": _round(pnl, 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                "r_multiple": _round(_r_multiple(trade), 6),
                "win": bool(pnl is not None and pnl > 0),
                **state,
            }
        )
    coverage = {
        "trades_total": len(result.get("trades") or []),
        "trades_with_state": len(rows),
        "trades_missing_state": missing_state,
        "state_coverage_rate": _round(
            len(rows) / len(result.get("trades") or []), 4
        )
        if result.get("trades")
        else None,
    }
    return rows, coverage


def _router_readiness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(row["strategy_family"] for row in rows)
    state_counts = Counter(row["combined_state"] for row in rows)
    family_state_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        family_state_counts[row["strategy_family"]][row["combined_state"]] += 1
    total_trades = len(rows)
    candidates: list[dict[str, Any]] = []
    failed: list[str] = []
    if total_trades < MIN_TOTAL_TRADES_FOR_ROUTER:
        failed.append("core_trade_sample_below_router_minimum")
    if sum(1 for count in family_counts.values() if count >= MIN_FAMILY_TRADES_FOR_ROUTER) < 2:
        failed.append("fewer_than_two_families_have_minimum_sample")
    families_with_state_contrast = sum(
        1
        for counts in family_state_counts.values()
        if sum(
            1
            for count in counts.values()
            if count >= MIN_STATE_FAMILY_TRADES_GLOBAL
        )
        >= 2
    )
    if families_with_state_contrast < 1:
        failed.append("state_contrast_sample_too_small")

    global_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_window_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["strategy_family"], row["combined_state"])
        global_groups[key].append(row)
        by_window_groups[(row["window"], *key)].append(row)

    for (family, state), group_rows in sorted(global_groups.items()):
        if len(group_rows) < MIN_STATE_FAMILY_TRADES_GLOBAL:
            continue
        comparator_rows = [
            row
            for row in rows
            if row["strategy_family"] == family and row["combined_state"] != state
        ]
        if len(comparator_rows) < MIN_STATE_FAMILY_TRADES_GLOBAL:
            continue
        global_summary = _summarize_rows(group_rows)
        comparator_summary = _summarize_rows(comparator_rows)
        edge_vs_same_family_other_states = None
        if (
            global_summary.get("avg_r") is not None
            and comparator_summary.get("avg_r") is not None
        ):
            edge_vs_same_family_other_states = (
                float(global_summary["avg_r"]) - float(comparator_summary["avg_r"])
            )
        window_summaries = {
            window: _summarize_rows(window_rows)
            for (window, group_family, group_state), window_rows in by_window_groups.items()
            if group_family == family and group_state == state
        }
        positive_windows = sum(
            1
            for summary in window_summaries.values()
            if summary.get("avg_r") is not None and summary["avg_r"] > 0
        )
        windows_with_sample = sum(
            1 for summary in window_summaries.values() if summary.get("trades", 0) > 0
        )
        if (
            global_summary.get("avg_r") is not None
            and global_summary["avg_r"] > 0
            and edge_vs_same_family_other_states is not None
            and edge_vs_same_family_other_states >= MIN_STATE_FAMILY_R_EDGE
            and windows_with_sample >= MIN_WINDOWS_WITH_STATE_FAMILY
            and positive_windows >= MIN_WINDOWS_WITH_STATE_FAMILY
        ):
            candidates.append(
                {
                    "strategy_family": family,
                    "combined_state": state,
                    "global": global_summary,
                    "same_family_other_states": comparator_summary,
                    "edge_vs_same_family_other_states_avg_r": _round(
                        edge_vs_same_family_other_states, 4
                    ),
                    "windows_with_sample": windows_with_sample,
                    "positive_windows": positive_windows,
                    "window_summaries": window_summaries,
                }
            )

    candidates.sort(
        key=lambda row: (
            -float(row["global"].get("avg_r") or 0.0),
            -int(row["global"].get("trades") or 0),
            row["strategy_family"],
            row["combined_state"],
        )
    )
    if not candidates:
        failed.append("no_stable_positive_state_family_candidate")
    ready = not failed
    return {
        "ready_for_router_gate": ready,
        "decision": (
            "observed_only_router_candidate_requires_frozen_gate_1_4"
            if ready
            else "observed_only_no_router_yet_market_state_sample_thin_or_unstable"
        ),
        "failed_reasons": failed,
        "thresholds": {
            "min_total_trades_for_router": MIN_TOTAL_TRADES_FOR_ROUTER,
            "min_family_trades_for_router": MIN_FAMILY_TRADES_FOR_ROUTER,
            "min_state_family_trades_global": MIN_STATE_FAMILY_TRADES_GLOBAL,
            "min_windows_with_state_family": MIN_WINDOWS_WITH_STATE_FAMILY,
            "min_state_family_r_edge": MIN_STATE_FAMILY_R_EDGE,
        },
        "total_trades": total_trades,
        "family_counts": dict(sorted(family_counts.items())),
        "state_counts": dict(sorted(state_counts.items())),
        "family_state_counts": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(family_state_counts.items())
        },
        "families_with_state_contrast": families_with_state_contrast,
        "candidate_count": len(candidates),
        "top_candidates": candidates[:10],
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    universe = sorted(get_universe())
    windows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    all_rows: list[dict[str, Any]] = []

    for label, cfg in WINDOWS.items():
        print(f"[{label}] canonical core baseline + market-state attribution")
        result = _run_baseline(universe, cfg)
        snapshot = _load_snapshot(cfg["snapshot"])
        rows, coverage = _extract_window_rows(
            label=label,
            cfg=cfg,
            result=result,
            snapshot=snapshot,
        )
        all_rows.extend(rows)
        windows[label] = {
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "baseline_metrics": _metrics(result),
            "coverage": coverage,
            "summary_by_strategy_family": _group_summary(rows, ["strategy_family"]),
            "summary_by_regime": _group_summary(rows, ["regime"]),
            "summary_by_sentiment": _group_summary(rows, ["sentiment"]),
            "summary_by_combined_state": _group_summary(rows, ["combined_state"]),
            "summary_by_family_and_state": _group_summary(
                rows, ["strategy_family", "combined_state"]
            ),
            "sample_rows": rows[:40],
        }
        print(
            f"  trades={coverage['trades_total']} state={coverage['trades_with_state']} "
            f"families={dict(Counter(row['strategy_family'] for row in rows))}"
        )

    aggregate_metrics = {
        "expected_value_score_sum": _round(
            sum(
                float(window["baseline_metrics"]["expected_value_score"] or 0.0)
                for window in windows.values()
            ),
            4,
        ),
        "total_pnl_sum": _round(
            sum(
                float(window["baseline_metrics"]["total_pnl"] or 0.0)
                for window in windows.values()
            ),
            2,
        ),
        "trade_count": len(all_rows),
        "state_coverage_rate": _round(
            len(all_rows)
            / sum(window["coverage"]["trades_total"] for window in windows.values()),
            4,
        ),
    }
    readiness = _router_readiness(all_rows)
    status = "observed_only"
    decision = readiness["decision"]
    if readiness["ready_for_router_gate"]:
        interpretation = (
            "Observed-only attribution found enough stable state-family "
            "separation to justify a separate frozen router Gate 1-4 experiment. "
            "No router is enabled in this run."
        )
    else:
        interpretation = (
            "Observed-only attribution does not yet justify a state-conditioned "
            "family router. The core sample is small and/or the state-family "
            "effect is not stable enough across canonical windows."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_discovery",
        "status": status,
        "decision": decision,
        "accepted": False,
        "diagnostic_only": True,
        "hypothesis": (
            "Market state known before entry may predict which strategy family "
            "has positive realized trade value, enabling a later "
            "state-conditioned router without changing live orders today."
        ),
        "change_type": "read_only_market_state_family_attribution",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "market_state_family_replacement_value_prediction",
        "new_evidence_type": "read_only_state_family_monotonicity_attribution",
        "nearby_prior_experiments": [
            "exp-20260511-017",
            "exp-20260526-021",
            "exp-20260528-035",
            "exp-20260528-036",
            "exp-20260530-002",
            "exp-20260606-014",
        ],
        "prior_trial_count": 6,
        "multiple_testing_risk_bucket": "moderate",
        "prediction": PREDICTION,
        "production_impact": PRODUCTION_IMPACT,
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three fixed windows",
            "warehouse": _repo_rel(WAREHOUSE),
            "windows": WINDOWS,
            "state_timing": "prior_trading_day_close_before_entry_open",
            "baseline_result_file": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/risk allocation precursor: market-state buckets may "
                "select which strategy family deserves capital in a later "
                "router."
            ),
            "2_history_check": (
                "Related market-state/state-surface and broad-continuation "
                "experiments exist. Recent state-gated broad continuation "
                "variants improved aggregate EV but failed old_thin/tail "
                "guards, motivating family-level attribution instead of "
                "another threshold retune."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: require three-window coverage and stable "
                "state-family separation before opening a separate frozen "
                "router Gate 1-4 experiment. This run cannot be accepted as a "
                "production alpha because it changes no trading behavior."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260606_021_market_state_family_replacement_value_attribution.py"
            ),
        },
        "windows": windows,
        "aggregate_baseline_metrics": aggregate_metrics,
        "aggregate_summary_by_strategy_family": _group_summary(
            all_rows, ["strategy_family"]
        ),
        "aggregate_summary_by_regime": _group_summary(all_rows, ["regime"]),
        "aggregate_summary_by_sentiment": _group_summary(all_rows, ["sentiment"]),
        "aggregate_summary_by_combined_state": _group_summary(
            all_rows, ["combined_state"]
        ),
        "aggregate_summary_by_family_and_state": _group_summary(
            all_rows, ["strategy_family", "combined_state"]
        ),
        "router_readiness": readiness,
        "interpretation": interpretation,
        "negative_reflection": (
            "If this remains no-router, the reason is not a coding bug: the "
            "canonical core trade sample is too small and the state-family "
            "separation is not stable enough to justify routing capital. The "
            "next credible step is to expand attribution to default-off "
            "paper sleeves or forward replacement-value rows, not to fit a "
            "router on sparse core trades."
        ),
        "next_experiment_hint": (
            "Extend the same PIT state labeling to accepted default-off paper "
            "sleeve closed rows and compute family replacement value versus "
            "cash/core displacement before testing any frozen state router."
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
        "aggregate_baseline_metrics": payload["aggregate_baseline_metrics"],
        "router_readiness": payload["router_readiness"],
        "windows": [
            {
                "label": label,
                "expected_value_score": window["baseline_metrics"][
                    "expected_value_score"
                ],
                "total_pnl": window["baseline_metrics"]["total_pnl"],
                "trade_count": window["baseline_metrics"]["trade_count"],
                "state_coverage_rate": window["coverage"]["state_coverage_rate"],
                "summary_by_family": window["summary_by_strategy_family"],
            }
            for label, window in payload["windows"].items()
        ],
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_gate4_passed": False,
            "failure_modes_observed": payload["router_readiness"]["failed_reasons"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | EV | PnL | Trades | State Cov | Top Family | Top State |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for label, window in payload["windows"].items():
        family_summary = window["summary_by_strategy_family"]
        top_family = max(
            family_summary.items(),
            key=lambda item: float(item[1].get("total_pnl") or 0.0),
        )[0] if family_summary else "n/a"
        state_summary = window["summary_by_combined_state"]
        top_state = max(
            state_summary.items(),
            key=lambda item: float(item[1].get("avg_r") or -999.0),
        )[0] if state_summary else "n/a"
        rows.append(
            "| {label} | {ev:.4f} | ${pnl:,.2f} | {trades} | {cov:.2%} | {family} | {state} |".format(
                label=label,
                ev=float(window["baseline_metrics"]["expected_value_score"] or 0.0),
                pnl=float(window["baseline_metrics"]["total_pnl"] or 0.0),
                trades=int(window["baseline_metrics"]["trade_count"] or 0),
                cov=float(window["coverage"]["state_coverage_rate"] or 0.0),
                family=top_family,
                state=top_state.replace("|", "/"),
            )
        )

    readiness = payload["router_readiness"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Market-State Family Attribution",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Three-Window Baseline Attribution",
            "",
            *rows,
            "",
            "## Router Readiness",
            "",
            f"- Ready for router Gate 1-4: `{readiness['ready_for_router_gate']}`",
            f"- Failed reasons: `{', '.join(readiness['failed_reasons']) or 'none'}`",
            f"- Total trades with state: `{readiness['total_trades']}`",
            f"- Family counts: `{readiness['family_counts']}`",
            f"- Candidate state-family cells: `{readiness['candidate_count']}`",
            "",
            "## Conclusion",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            (
                "Observed-only. No shared policy, run adapter, backtester adapter, "
                "watchlist, order path, core entry, ranking, sizing, or exit "
                "behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
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
                "router_readiness": payload["router_readiness"],
                "aggregate_baseline_metrics": payload["aggregate_baseline_metrics"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    else:
        registry = {"schema_version": 1, "experiments": []}
    experiments = registry.setdefault("experiments", [])
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
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(_safe(registry), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
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
        "file_hashes": {
            _repo_rel(Path(__file__)): _sha256(Path(__file__)),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    persist(payload)
    print(json.dumps(_safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
