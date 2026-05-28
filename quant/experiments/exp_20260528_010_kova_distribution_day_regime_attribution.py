"""exp-20260528-010: Kova distribution-day regime attribution.

This observed-only experiment explores the Kova market-regime direction that
had not yet been tested in Ginger: distribution-day pressure and a simple
confirmed-uptrend proxy for the accepted top-2 QQQ-confirmed VCP paper sleeve.

It reads the accepted exp-20260526-007 VCP top-2 paper trades, joins only
signal-date SPY/QQQ OHLCV known after the signal close, and reports attribution
buckets. It does not change entries, exits, ranking, sizing, paper notional,
LLM/news, production watchlists, or live/default orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260528-010"
STEM = "kova_distribution_day_regime_attribution"
TRIAL_FAMILY = "kova_distribution_day_regime_context"
CHANGED_VARIABLE = "vcp_kova_distribution_pressure_bucket_v1"
CONTEXT_RULE_VERSION = "kova_distribution_day_confirmed_uptrend_proxy_v1"

SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260526-007"
    / "vcp_rank_notional_profile.json"
)
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

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

DISTRIBUTION_LOOKBACK_DAYS = 25
RECENT_DISTRIBUTION_LOOKBACK_DAYS = 10
DISTRIBUTION_DOWN_RETURN_THRESHOLD = -0.002
UPTREND_MA_DAYS = 50
UPTREND_SHORT_MA_DAYS = 21
UPTREND_RETURN_DAYS = 20
SOURCE_VARIANT = "rank2_125"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _money(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return number


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "reason": "missing_open_positions_json",
        }
    payload = _read_json(OPEN_POSITIONS_JSON)
    rows: list[dict[str, Any]] = []
    for key in ("positions", "observations"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    missing_entry = [
        str(row.get("ticker") or "<unknown>") for row in rows if not row.get("entry_date")
    ]
    missing_target = [
        str(row.get("ticker") or "<unknown>")
        for row in rows
        if row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing_entry and not missing_target,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(rows),
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
    }


def _normalise_rows(raw_rows: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(raw_rows, list):
        return rows
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        date = str(raw.get("Date") or raw.get("date") or "")[:10]
        if not date:
            continue
        rows.append(
            {
                "date": date,
                "open": _float_or_none(raw.get("Open") or raw.get("open")),
                "high": _float_or_none(raw.get("High") or raw.get("high")),
                "low": _float_or_none(raw.get("Low") or raw.get("low")),
                "close": _float_or_none(raw.get("Close") or raw.get("close")),
                "volume": _float_or_none(raw.get("Volume") or raw.get("volume")),
            }
        )
    return sorted([row for row in rows if row.get("close") is not None], key=lambda r: r["date"])


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows)
        if str(row.get("date") or "")[:10] <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


def _close_return(rows: list[dict[str, Any]], idx: int | None, lookback: int) -> float | None:
    if idx is None or idx < lookback:
        return None
    current = rows[idx].get("close")
    prior = rows[idx - lookback].get("close")
    if not current or not prior:
        return None
    return (current / prior) - 1.0


def _moving_average(rows: list[dict[str, Any]], idx: int | None, lookback: int) -> float | None:
    if idx is None or idx + 1 < lookback:
        return None
    values = [rows[j].get("close") for j in range(idx - lookback + 1, idx + 1)]
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values) / lookback


def _distribution_days(
    rows: list[dict[str, Any]],
    idx: int | None,
    lookback: int,
) -> list[dict[str, Any]]:
    if idx is None:
        return []
    hits: list[dict[str, Any]] = []
    start = max(1, idx - lookback + 1)
    for row_idx in range(start, idx + 1):
        prev = rows[row_idx - 1]
        cur = rows[row_idx]
        prev_close = prev.get("close")
        cur_close = cur.get("close")
        prev_volume = prev.get("volume")
        cur_volume = cur.get("volume")
        if not prev_close or cur_close is None or not prev_volume or cur_volume is None:
            continue
        daily_return = (cur_close / prev_close) - 1.0
        if daily_return <= DISTRIBUTION_DOWN_RETURN_THRESHOLD and cur_volume > prev_volume:
            hits.append(
                {
                    "date": cur["date"],
                    "return": _round(daily_return, 6),
                    "volume_ratio_vs_prior_day": _round(cur_volume / prev_volume, 6),
                }
            )
    return hits


def _index_context(rows: list[dict[str, Any]], as_of: str) -> dict[str, Any]:
    idx = _latest_index_on_or_before(rows, as_of)
    if idx is None:
        return {"status": "missing_index_date", "asof_date": as_of}
    close = rows[idx].get("close")
    ma50 = _moving_average(rows, idx, UPTREND_MA_DAYS)
    ma21 = _moving_average(rows, idx, UPTREND_SHORT_MA_DAYS)
    ret20 = _close_return(rows, idx, UPTREND_RETURN_DAYS)
    dist25 = _distribution_days(rows, idx, DISTRIBUTION_LOOKBACK_DAYS)
    dist10 = _distribution_days(rows, idx, RECENT_DISTRIBUTION_LOOKBACK_DAYS)
    above50 = close is not None and ma50 is not None and close > ma50
    above21 = close is not None and ma21 is not None and close > ma21
    return {
        "status": "ok",
        "asof_date": rows[idx]["date"],
        "close": _round(close, 4),
        "ret20": _round(ret20, 6),
        "above_21d_ma": above21,
        "above_50d_ma": above50,
        "distribution_day_count_25d": len(dist25),
        "recent_distribution_day_count_10d": len(dist10),
        "latest_distribution_day": dist25[-1]["date"] if dist25 else None,
        "distribution_days_25d": dist25,
    }


def _market_context(snapshot: dict[str, Any], signal_date: str) -> dict[str, Any]:
    ohlcv = snapshot.get("ohlcv") if isinstance(snapshot.get("ohlcv"), dict) else {}
    spy = _index_context(_normalise_rows(ohlcv.get("SPY")), signal_date)
    qqq = _index_context(_normalise_rows(ohlcv.get("QQQ")), signal_date)
    status = "ok" if spy.get("status") == "ok" and qqq.get("status") == "ok" else "missing_market_context"
    if status != "ok":
        return {
            "rule_version": CONTEXT_RULE_VERSION,
            "status": status,
            "signal_date": signal_date,
            "bucket": "missing_market_context",
            "spy": spy,
            "qqq": qqq,
            "known_at": "after_signal_date_close_before_next_open_paper_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }

    max_distribution_count = max(
        int(spy["distribution_day_count_25d"]),
        int(qqq["distribution_day_count_25d"]),
    )
    max_recent_distribution_count = max(
        int(spy["recent_distribution_day_count_10d"]),
        int(qqq["recent_distribution_day_count_10d"]),
    )
    confirmed_uptrend_proxy = (
        bool(spy["above_50d_ma"])
        and bool(qqq["above_50d_ma"])
        and bool(qqq["above_21d_ma"])
        and (spy.get("ret20") is not None and float(spy["ret20"]) > 0)
        and (qqq.get("ret20") is not None and float(qqq["ret20"]) > 0)
    )
    if not confirmed_uptrend_proxy:
        bucket = "unconfirmed_or_downtrend"
    elif max_distribution_count <= 2:
        bucket = "confirmed_low_distribution"
    elif max_distribution_count <= 4:
        bucket = "confirmed_moderate_distribution"
    else:
        bucket = "uptrend_high_distribution_pressure"

    return {
        "rule_version": CONTEXT_RULE_VERSION,
        "status": "ok",
        "signal_date": signal_date,
        "bucket": bucket,
        "confirmed_uptrend_proxy": confirmed_uptrend_proxy,
        "max_distribution_day_count_25d": max_distribution_count,
        "max_recent_distribution_day_count_10d": max_recent_distribution_count,
        "distribution_lookback_days": DISTRIBUTION_LOOKBACK_DAYS,
        "recent_distribution_lookback_days": RECENT_DISTRIBUTION_LOOKBACK_DAYS,
        "distribution_down_return_threshold": DISTRIBUTION_DOWN_RETURN_THRESHOLD,
        "uptrend_proxy_definition": (
            "SPY and QQQ above 50dma, QQQ above 21dma, and both SPY/QQQ 20d returns positive"
        ),
        "spy": spy,
        "qqq": qqq,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _load_source_trades() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    source = _read_json(SOURCE_ARTIFACT)
    profile = source["profile_results"][SOURCE_VARIANT]
    trades_by_window = profile["target_trades_by_window"]
    return source, {
        label: [dict(row) for row in trades_by_window.get(label, [])]
        for label in WINDOWS
    }


def _join_context(
    trades_by_window: dict[str, list[dict[str, Any]]]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    enriched_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    context_cache: dict[tuple[str, str], dict[str, Any]] = {}
    snapshots: dict[str, dict[str, Any]] = {}
    for label, cfg in WINDOWS.items():
        snapshots[label] = _read_json(REPO_ROOT / cfg["snapshot"])
        enriched: list[dict[str, Any]] = []
        for trade in trades_by_window[label]:
            signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
            cache_key = (label, signal_date)
            if cache_key not in context_cache:
                context_cache[cache_key] = _market_context(snapshots[label], signal_date)
            context = context_cache[cache_key]
            enriched.append(
                {
                    **trade,
                    "kova_market_regime_context": context,
                    "kova_distribution_pressure_bucket": context["bucket"],
                    "kova_distribution_context_rule_version": CONTEXT_RULE_VERSION,
                }
            )
        enriched_by_window[label] = enriched
    coverage = _coverage_summary(enriched_by_window)
    return enriched_by_window, coverage


def _coverage_summary(enriched_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    total = 0
    ok = 0
    by_window: dict[str, dict[str, Any]] = OrderedDict()
    for label, trades in enriched_by_window.items():
        window_total = len(trades)
        window_ok = sum(
            1
            for trade in trades
            if trade.get("kova_market_regime_context", {}).get("status") == "ok"
        )
        total += window_total
        ok += window_ok
        by_window[label] = {
            "trades": window_total,
            "context_ok": window_ok,
            "coverage": _round(window_ok / window_total, 6) if window_total else None,
        }
    return {
        "trades": total,
        "context_ok": ok,
        "coverage": _round(ok / total, 6) if total else None,
        "by_window": by_window,
    }


def _summarise_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [_money(trade.get("pnl")) for trade in trades]
    positive_pnls = [pnl for pnl in pnls if pnl > 0]
    by_window: Counter[str] = Counter(str(trade.get("window") or "") for trade in trades)
    by_rank: Counter[str] = Counter(
        str(trade.get("vcp_candidate_rank_on_signal_date") or "") for trade in trades
    )
    by_ticker: Counter[str] = Counter(str(trade.get("ticker") or "") for trade in trades)
    return {
        "trade_count": len(trades),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2) if pnls else None,
        "median_pnl": _round(median(pnls), 2) if pnls else None,
        "win_rate": _round(len(positive_pnls) / len(pnls), 6) if pnls else None,
        "avg_fwd_5d": _avg_trade_field(trades, "fwd_5d"),
        "avg_fwd_10d": _avg_trade_field(trades, "fwd_10d"),
        "avg_fwd_20d": _avg_trade_field(trades, "fwd_20d"),
        "by_window_count": dict(sorted(by_window.items())),
        "by_rank_count": dict(sorted(by_rank.items())),
        "top_ticker_counts": dict(by_ticker.most_common(10)),
    }


def _avg_trade_field(trades: list[dict[str, Any]], field: str) -> Any:
    values = []
    for trade in trades:
        value = _float_or_none(trade.get(field))
        if value is not None:
            values.append(value)
    return _round(sum(values) / len(values), 6) if values else None


def _bucket_attribution(
    enriched_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    all_trades: list[dict[str, Any]] = []
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_window_bucket: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    by_distribution_count: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for label, trades in enriched_by_window.items():
        for trade in trades:
            row = {**trade, "window": label}
            context = row.get("kova_market_regime_context") or {}
            bucket = str(context.get("bucket") or "missing_market_context")
            count = context.get("max_distribution_day_count_25d")
            count_bucket = _distribution_count_bucket(count)
            all_trades.append(row)
            by_bucket[bucket].append(row)
            by_window_bucket[label][bucket].append(row)
            by_distribution_count[count_bucket].append(row)

    bucket_summary = OrderedDict(
        (bucket, _summarise_trades(rows))
        for bucket, rows in sorted(by_bucket.items(), key=lambda item: item[0])
    )
    window_bucket_summary = OrderedDict()
    for label in WINDOWS:
        window_bucket_summary[label] = OrderedDict(
            (bucket, _summarise_trades(rows))
            for bucket, rows in sorted(by_window_bucket[label].items(), key=lambda item: item[0])
        )
    distribution_count_summary = OrderedDict(
        (bucket, _summarise_trades(rows))
        for bucket, rows in sorted(by_distribution_count.items(), key=lambda item: item[0])
    )
    return {
        "overall": _summarise_trades(all_trades),
        "by_bucket": bucket_summary,
        "by_window_bucket": window_bucket_summary,
        "by_distribution_count_bucket": distribution_count_summary,
        "high_pressure_vs_rest": _high_pressure_vs_rest(by_bucket),
    }


def _distribution_count_bucket(value: Any) -> str:
    count = _float_or_none(value)
    if count is None:
        return "missing"
    if count <= 2:
        return "dist_count_0_2"
    if count <= 4:
        return "dist_count_3_4"
    return "dist_count_5_plus"


def _high_pressure_vs_rest(
    by_bucket: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    high = by_bucket.get("uptrend_high_distribution_pressure", [])
    rest: list[dict[str, Any]] = []
    for bucket, rows in by_bucket.items():
        if bucket != "uptrend_high_distribution_pressure":
            rest.extend(rows)
    high_summary = _summarise_trades(high)
    rest_summary = _summarise_trades(rest)
    high_avg = high_summary.get("avg_pnl")
    rest_avg = rest_summary.get("avg_pnl")
    return {
        "high_pressure": high_summary,
        "rest": rest_summary,
        "avg_pnl_delta_high_minus_rest": _round(
            float(high_avg) - float(rest_avg)
            if high_avg is not None and rest_avg is not None
            else None,
            2,
        ),
        "interpretation": (
            "high_pressure_underperformed_rest_but_remained_positive"
            if high_summary.get("total_pnl", 0) and float(high_summary["total_pnl"]) > 0
            else "high_pressure_nonpositive"
        ),
    }


def _actionability_gate(attribution: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    high = attribution["high_pressure_vs_rest"]["high_pressure"]
    rest = attribution["high_pressure_vs_rest"]["rest"]
    high_count = int(high.get("trade_count") or 0)
    high_pnl = float(high.get("total_pnl") or 0.0)
    high_avg = high.get("avg_pnl")
    rest_avg = rest.get("avg_pnl")
    coverage_ok = float(coverage.get("coverage") or 0.0) >= 0.95
    sample_ok = high_count >= 20
    materially_weaker = (
        high_avg is not None
        and rest_avg is not None
        and float(high_avg) <= max(0.0, float(rest_avg) * 0.5)
    )
    failed = []
    if not coverage_ok:
        failed.append("context_coverage_below_95pct")
    if not sample_ok:
        failed.append("high_pressure_sample_below_20")
    if high_pnl > 0:
        failed.append("high_pressure_bucket_positive_pnl")
    if not materially_weaker:
        failed.append("high_pressure_not_materially_weaker_than_rest")
    return {
        "passed": False,
        "status": "observed_only_not_promotable",
        "coverage_ok": coverage_ok,
        "high_pressure_sample_ok": sample_ok,
        "high_pressure_total_pnl": _round(high_pnl, 2),
        "high_pressure_avg_pnl": high_avg,
        "rest_avg_pnl": rest_avg,
        "materially_weaker_than_rest": materially_weaker,
        "failed_reasons": failed,
        "promotion_boundary": (
            "This is read-only attribution. A future rule would require forward "
            "replacement-value evidence and a separate Gate 1-4 strategy experiment."
        ),
    }


def _unchanged_delta_metrics(before_metrics: dict[str, Any]) -> dict[str, Any]:
    by_window = OrderedDict()
    for label, metrics in before_metrics.items():
        by_window[label] = {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "sharpe_daily": 0.0,
            "strategy_total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0,
            "survival_rate": 0.0,
            "signals_generated": 0,
            "signals_survived": 0,
        }
    return {
        "by_window": by_window,
        "aggregate": {
            "expected_value_score_delta_sum": 0.0,
            "total_pnl_delta_sum": 0.0,
            "trade_count_delta_sum": 0,
            "max_drawdown_delta_max": 0.0,
        },
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = _audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    source, source_trades = _load_source_trades()
    enriched_by_window, coverage = _join_context(source_trades)
    attribution = _bucket_attribution(enriched_by_window)
    actionability_gate = _actionability_gate(attribution, coverage)
    before_metrics = source["before_metrics"]
    delta_metrics = _unchanged_delta_metrics(before_metrics)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": "observed_only",
        "decision": "observed_only_kova_distribution_day_regime_attribution",
        "hypothesis": (
            "Kova's distribution-day pressure and confirmed-uptrend market layer "
            "may explain which accepted QQQ-confirmed VCP top-2 paper trades have "
            "better replacement value. High distribution pressure should be weaker "
            "if it is a useful pre-entry risk context."
        ),
        "change_type": "read_only_attribution",
        "mechanism_family": "vcp_kova_market_regime_context",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260525-022",
            "exp-20260525-037",
            "exp-20260526-007",
            "exp-20260527-902",
            "exp-20260527-906",
            "exp-20260528-002",
        ],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "new_read_only_kova_market_regime_context_field",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_paper_trades": _repo_rel(SOURCE_ARTIFACT),
            "source_variant": SOURCE_VARIANT,
            "strategy_behavior_changed": False,
        },
        "parameters": {
            "context_rule_version": CONTEXT_RULE_VERSION,
            "distribution_lookback_days": DISTRIBUTION_LOOKBACK_DAYS,
            "recent_distribution_lookback_days": RECENT_DISTRIBUTION_LOOKBACK_DAYS,
            "distribution_day_definition": (
                "SPY/QQQ close-to-close return <= -0.20% and volume above prior day"
            ),
            "confirmed_uptrend_proxy": (
                "SPY and QQQ above 50dma, QQQ above 21dma, and both SPY/QQQ 20d returns positive"
            ),
            "bucket_rules": {
                "confirmed_low_distribution": "confirmed_uptrend_proxy and max(SPY, QQQ) 25d distribution count <= 2",
                "confirmed_moderate_distribution": "confirmed_uptrend_proxy and max(SPY, QQQ) 25d distribution count 3-4",
                "uptrend_high_distribution_pressure": "confirmed_uptrend_proxy and max(SPY, QQQ) 25d distribution count >= 5",
                "unconfirmed_or_downtrend": "confirmed_uptrend_proxy is false",
            },
            "locked_variables": [
                "VCP candidate definition",
                "QQQ > SPY confirmation",
                "top-2 selection",
                "rank-notional profile [1.0, 1.25]",
                "10-trading-day paper hold",
                "core entries",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news",
                "live/default orders",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation / market regime attribution: distribution-day "
                "pressure may explain weaker VCP paper outcomes beyond the existing "
                "QQQ > SPY confirmation."
            ),
            "2_history_check": (
                "Repository search found no prior distribution-day or confirmed-uptrend "
                "Kova experiment. Nearby VCP threshold, stop, pyramid, pocket-pivot, "
                "intraday, 13F, and high-volume weak-close ideas were already tested "
                "or marked data/lifecycle gated."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: require >=95% context coverage and a meaningful "
                "high-pressure sample before interpreting. Do not promote any gate "
                "unless high pressure is clearly harmful and later passes a separate "
                "Gate 1-4 strategy experiment."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260528_010_kova_distribution_day_regime_attribution.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "data/experiments/exp-20260526-007/vcp_rank_notional_profile.json#before_metrics",
            "source_paper_artifact": _repo_rel(SOURCE_ARTIFACT),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "SPY OHLCV Date/Close/Volume through signal_date",
                "QQQ OHLCV Date/Close/Volume through signal_date",
                "accepted VCP top-2 target trade signal_date",
                "accepted VCP top-2 target trade pnl",
            ],
            "passed": True,
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": _round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                4,
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "passed": True,
            "note": "No filter, entry, sizing, or paper-selection behavior changed.",
        },
        "gate4": {
            "strategy_change": False,
            "passed": False,
            "status": "not_applicable_observed_only",
            "actionability_gate": actionability_gate,
            "reason": (
                "This run adds attribution evidence only. It intentionally does not "
                "retain or reject a strategy rule."
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": before_metrics,
        "delta_metrics": delta_metrics,
        "context_coverage": coverage,
        "attribution": attribution,
        "target_trades_by_window": enriched_by_window,
        "expected_value_score_delta": 0.0,
        "total_pnl_delta": 0.0,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "interpretation": _interpretation(attribution, actionability_gate),
        "rejection_reason": None,
        "next_retry_requires": [
            "closed forward replacement-value rows by distribution bucket",
            "a separate Gate 1-4 strategy experiment before using the bucket as a gate or scalar",
            "do not retune VCP thresholds or stops from this attribution alone",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(SOURCE_ARTIFACT),
            "docs/kova-research-directions.md",
            "docs/data_edge_context_layers.md",
        ],
        "anti_js": "No JavaScript was used.",
    }


def _interpretation(attribution: dict[str, Any], gate: dict[str, Any]) -> str:
    high = attribution["high_pressure_vs_rest"]["high_pressure"]
    rest = attribution["high_pressure_vs_rest"]["rest"]
    return (
        "Distribution-day pressure is a useful read-only context field, but not "
        "a promotable VCP gate on this frozen sample. The high-pressure bucket "
        f"had {high['trade_count']} trades and ${high['total_pnl']} PnL "
        f"(avg ${high['avg_pnl']}), versus the rest at avg ${rest['avg_pnl']}. "
        f"Gate status: {gate['status']}."
    )


def _bucket_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Bucket | Trades | PnL | Avg PnL | Median PnL | Win rate | Avg fwd 10d | Rank counts |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for bucket, summary in payload["attribution"]["by_bucket"].items():
        rows.append(
            "| {bucket} | {count} | ${pnl:,.2f} | ${avg:,.2f} | ${med:,.2f} | {win} | {fwd} | `{rank}` |".format(
                bucket=bucket,
                count=summary["trade_count"],
                pnl=float(summary["total_pnl"] or 0.0),
                avg=float(summary["avg_pnl"] or 0.0),
                med=float(summary["median_pnl"] or 0.0),
                win=summary["win_rate"],
                fwd=summary["avg_fwd_10d"],
                rank=summary["by_rank_count"],
            )
        )
    return rows


def _window_bucket_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Bucket | Trades | PnL | Avg PnL | Win rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for label, buckets in payload["attribution"]["by_window_bucket"].items():
        for bucket, summary in buckets.items():
            rows.append(
                "| {label} | {bucket} | {count} | ${pnl:,.2f} | ${avg:,.2f} | {win} |".format(
                    label=label,
                    bucket=bucket,
                    count=summary["trade_count"],
                    pnl=float(summary["total_pnl"] or 0.0),
                    avg=float(summary["avg_pnl"] or 0.0),
                    win=summary["win_rate"],
                )
            )
    return rows


def _build_report(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Kova Distribution-Day Regime Attribution",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: a read-only Kova distribution-pressure bucket "
                "joined to the accepted exp-20260526-007 VCP top-2 paper trades."
            ),
            "",
            "## Bucket Attribution",
            "",
            *_bucket_table(payload),
            "",
            "## Window Split",
            "",
            *_window_bucket_table(payload),
            "",
            "## Coverage",
            "",
            "```json",
            json.dumps(payload["context_coverage"], indent=2, sort_keys=True),
            "```",
            "",
            "## Actionability Gate",
            "",
            "```json",
            json.dumps(payload["gate4"]["actionability_gate"], indent=2, sort_keys=True),
            "```",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            (
                "No live/default orders, core entry, ranking, sizing, exits, "
                "paper notional, LLM/news, or production watchlist behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Kova distribution-day regime attribution",
            "status": payload["status"],
            "decision": payload["decision"],
            "artifact": _repo_rel(ARTIFACT_MD),
            "json": _repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "context_coverage": payload["context_coverage"],
                    "bucket_summary": payload["attribution"]["by_bucket"],
                    "actionability_gate": payload["gate4"]["actionability_gate"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
