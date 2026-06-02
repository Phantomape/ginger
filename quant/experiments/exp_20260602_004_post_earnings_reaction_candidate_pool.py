"""exp-20260602-004: post-earnings reaction candidate-pool scout.

This replay-only alpha scout tests whether the new explicit PIT-safe
post-earnings continuation surface can support a default-off paper candidate
pool beyond core-selected trades. It does not alter core entries, ranking,
sizing, exits, LLM/news, watchlists, or live/default orders.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
QUANT_DIR = ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from quant.constants import ROUND_TRIP_COST_PCT  # noqa: E402
from quant.data_layer import get_universe  # noqa: E402
from quant.experiments import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage  # noqa: E402


EXPERIMENT_ID = "exp-20260602-004"
STEM = "post_earnings_reaction_candidate_pool"
TRIAL_FAMILY = "post_earnings_reaction_candidate_pool"
TRIAL_VARIANT_ID = "event_day_reaction_rs_top1_10d"
CHANGED_VARIABLE = "post_earnings_reaction_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

BASELINE_EXPERIMENT_ID = "exp-20260602-003"
BASELINE_FILES = OrderedDict(
    [
        ("late_strong", ROOT / "data/experiments/exp-20260602-003/late_strong_after.json"),
        ("mid_weak", ROOT / "data/experiments/exp-20260602-003/mid_weak_after.json"),
        ("old_thin", ROOT / "data/experiments/exp-20260602-003/old_thin_after.json"),
    ]
)

BASE_NOTIONAL_USD = 10_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
MIN_CLOSE = 5.0
MIN_AVG_DOLLAR_VOLUME_20 = 40_000_000.0
MIN_EVENT_RETURN = 0.01
MIN_EVENT_EXCESS_RETURN_VS_SPY = 0.005
MIN_RS20_VS_SPY = 0.0
MIN_CLOSE_LOCATION = 0.60
MA_DAYS = 50
RS_DAYS = 20
ADV_DAYS = 20

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30
CANONICAL_DOC_EV = 7.8941
CANONICAL_DOC_PNL = 234_850.99

STOCK_EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "USO",
    "UUP",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_004_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"
OPEN_POSITIONS_JSON = ROOT / "operator_inputs" / "open_positions.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _complete_expected_value(metrics: dict[str, Any]) -> dict[str, Any]:
    out = dict(metrics)
    if out.get("expected_value_score") is None:
        strategy_return = out.get("strategy_total_return_pct")
        sharpe_daily = out.get("sharpe_daily")
        if isinstance(strategy_return, (int, float)) and isinstance(
            sharpe_daily, (int, float)
        ):
            out["expected_value_score"] = _round(strategy_return * sharpe_daily, 4)
    return out


def _metric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in [
        "expected_value_score",
        "total_pnl",
        "strategy_total_return_pct",
        "sharpe_daily",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    ]:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(
            after_value, (int, float)
        ):
            digits = 2 if key == "total_pnl" else 6
            out[key] = round(after_value - before_value, digits)
    return out


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = ROOT / value
    return str(value.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
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


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "reason": "missing_open_positions_json",
        }
    payload = _load_json(OPEN_POSITIONS_JSON)
    rows = []
    for key in ("positions", "observations"):
        value = payload.get(key)
        if isinstance(value, list):
            rows.extend(row for row in value if isinstance(row, dict))
    missing_entry = [
        str(row.get("ticker") or "<unknown>") for row in rows if not row.get("entry_date")
    ]
    missing_target = [
        str(row.get("ticker") or "<unknown>") for row in rows if row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing_entry and not missing_target,
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "position_count": len(rows),
        "missing_entry_date_tickers": missing_entry,
        "missing_target_price_tickers": missing_target,
    }


def _load_ohlcv_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    return payload.get("ohlcv") if isinstance(payload, dict) and "ohlcv" in payload else payload


def _rows(snapshot: dict[str, list[dict[str, Any]]], ticker: str) -> list[dict[str, Any]]:
    return sorted(snapshot.get(ticker.upper()) or [], key=lambda row: _date(row))


def _date(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    return _as_float(row.get(key) if key in row else row.get(key.lower()))


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows) if _date(row)}


def _load_earnings_snapshot(date_dash: str) -> tuple[dict[str, Any], str | None]:
    date_key = date_dash.replace("-", "")
    candidates = [
        ROOT / "data" / "daily" / "snapshots" / "earnings" / f"earnings_snapshot_{date_key}.json",
        ROOT / "data" / "daily" / "snapshots" / "earnings" / "legacy_root" / f"earnings_snapshot_{date_key}.json",
        ROOT / "data" / f"earnings_snapshot_{date_key}.json",
    ]
    for path in candidates:
        if path.exists():
            payload = _load_json(path)
            return payload.get("earnings") or {}, _repo_rel(path)
    return {}, None


def _daily_close_location(row: dict[str, Any]) -> float | None:
    high = _value(row, "High")
    low = _value(row, "Low")
    close = _value(row, "Close")
    if high is None or low is None or close is None or high <= low:
        return None
    return (close - low) / (high - low)


def _return_between(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx < 0 or start_idx >= len(rows) or end_idx >= len(rows):
        return None
    start = _value(rows[start_idx], "Close")
    end = _value(rows[end_idx], "Close")
    if not start or end is None:
        return None
    return (end / start) - 1.0


def _avg_dollar_volume(rows: list[dict[str, Any]], end_idx_exclusive: int, days: int) -> float | None:
    start_idx = end_idx_exclusive - days
    if start_idx < 0:
        return None
    values: list[float] = []
    for row in rows[start_idx:end_idx_exclusive]:
        close = _value(row, "Close")
        volume = _value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values) if values else None


def _ma(rows: list[dict[str, Any]], end_idx_exclusive: int, days: int) -> float | None:
    start_idx = end_idx_exclusive - days
    if start_idx < 0:
        return None
    closes = [_value(row, "Close") for row in rows[start_idx:end_idx_exclusive]]
    if any(close is None for close in closes):
        return None
    return sum(float(close) for close in closes) / len(closes)


def _paper_trade_from_candidate(
    rows: list[dict[str, Any]],
    signal_idx: int,
    candidate: dict[str, Any],
    window_end: str,
) -> dict[str, Any] | None:
    entry_idx = signal_idx + 1
    exit_idx = signal_idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    exit_date = _date(rows[exit_idx])
    if exit_date > window_end:
        return None
    entry_raw = _value(rows[entry_idx], "Open")
    exit_raw = _value(rows[exit_idx], "Close")
    if not entry_raw or not exit_raw:
        return None
    entry_price = apply_entry_fill(entry_raw)
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    return {
        **candidate,
        "entry_date": _date(rows[entry_idx]),
        "exit_date": exit_date,
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "paper_pnl": _round(pnl, 2),
    }


def _candidate_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float, str]:
    return (
        -float(row.get("event_excess_return_vs_spy") or 0.0),
        -float(row.get("event_return") or 0.0),
        -float(row.get("rs20_vs_spy") or 0.0),
        -float(row.get("avg_dollar_volume_20") or 0.0),
        str(row.get("ticker") or ""),
    )


def _select_candidates_for_window(
    label: str,
    cfg: dict[str, str],
    universe: set[str],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spy_rows = _rows(snapshot, "SPY")
    spy_index = _row_index(spy_rows)
    raw_candidates_by_day: OrderedDict[str, list[tuple[list[dict[str, Any]], int, dict[str, Any]]]] = OrderedDict()
    rejection_counts: Counter[str] = Counter()
    earnings_source_counts: Counter[str] = Counter()
    raw_event_count = 0
    event_snapshot_days = 0
    dates = sorted(set(spy_index))

    for signal_date in dates:
        if signal_date < cfg["start"] or signal_date > cfg["end"]:
            continue
        earnings, source_path = _load_earnings_snapshot(signal_date)
        if not earnings:
            rejection_counts["missing_earnings_snapshot"] += 1
            continue
        event_snapshot_days += 1
        if source_path:
            earnings_source_counts[source_path] += 1
        spy_idx = spy_index[signal_date]
        spy_event_return = _return_between(spy_rows, spy_idx - 1, spy_idx)
        spy_ret20 = _return_between(spy_rows, spy_idx - RS_DAYS, spy_idx)
        if spy_event_return is None or spy_ret20 is None:
            rejection_counts["missing_spy_return_context"] += 1
            continue
        for raw_ticker, event in sorted(earnings.items()):
            ticker = str(raw_ticker or "").upper()
            if ticker not in universe:
                rejection_counts["not_current_production_universe"] += 1
                continue
            if ticker in STOCK_EXCLUDED_TICKERS:
                rejection_counts["stock_exclusion"] += 1
                continue
            if event.get("days_to_earnings") != 0:
                continue
            raw_event_count += 1
            if event.get("eps_actual_last") is None:
                rejection_counts["missing_eps_actual_last"] += 1
                continue
            rows = _rows(snapshot, ticker)
            idx = _row_index(rows).get(signal_date)
            if idx is None:
                rejection_counts["missing_signal_day_ohlcv"] += 1
                continue
            close = _value(rows[idx], "Close")
            if close is None or close < MIN_CLOSE:
                rejection_counts["below_min_close"] += 1
                continue
            ma50 = _ma(rows, idx, MA_DAYS)
            if ma50 is None:
                rejection_counts["missing_ma50"] += 1
                continue
            if close <= ma50:
                rejection_counts["below_50d_trend"] += 1
                continue
            event_return = _return_between(rows, idx - 1, idx)
            ret20 = _return_between(rows, idx - RS_DAYS, idx)
            close_location = _daily_close_location(rows[idx])
            avg_dollar_volume = _avg_dollar_volume(rows, idx, ADV_DAYS)
            if (
                event_return is None
                or ret20 is None
                or close_location is None
                or avg_dollar_volume is None
            ):
                rejection_counts["missing_price_features"] += 1
                continue
            event_excess = event_return - spy_event_return
            rs20_vs_spy = ret20 - spy_ret20
            if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20:
                rejection_counts["low_avg_dollar_volume_20"] += 1
                continue
            if event_return < MIN_EVENT_RETURN:
                rejection_counts["weak_event_day_return"] += 1
                continue
            if event_excess < MIN_EVENT_EXCESS_RETURN_VS_SPY:
                rejection_counts["weak_event_day_excess_vs_spy"] += 1
                continue
            if rs20_vs_spy < MIN_RS20_VS_SPY:
                rejection_counts["weak_rs20_vs_spy"] += 1
                continue
            if close_location < MIN_CLOSE_LOCATION:
                rejection_counts["weak_event_day_close_location"] += 1
                continue
            candidate = {
                "ticker": ticker,
                "date": signal_date,
                "signal_date": signal_date,
                "strategy": "post_earnings_reaction_candidate_pool",
                "rule_version": RULE_VERSION,
                "candidate_pool_rule_version": RULE_VERSION,
                "known_at": "post-earnings event-day close before next-open paper entry",
                "trade_enabled": False,
                "alters_orders": False,
                "post_earnings_reaction_event_source": "earnings_snapshot_days_to_earnings_zero_with_eps_actual",
                "post_earnings_reaction_future_adapter_source": "post_earnings_continuation_confirmed_v1",
                "eps_actual_last": event.get("eps_actual_last"),
                "eps_estimate": event.get("eps_estimate"),
                "avg_historical_surprise_pct": event.get("avg_historical_surprise_pct"),
                "historical_surprise_pct": event.get("historical_surprise_pct") or [],
                "event_return": _round(event_return, 6),
                "spy_event_return": _round(spy_event_return, 6),
                "event_excess_return_vs_spy": _round(event_excess, 6),
                "ret20": _round(ret20, 6),
                "spy_ret20": _round(spy_ret20, 6),
                "rs20_vs_spy": _round(rs20_vs_spy, 6),
                "event_day_close_location": _round(close_location, 6),
                "avg_dollar_volume_20": _round(avg_dollar_volume, 2),
                "close": _round(close, 4),
                "ma50_prior": _round(ma50, 4),
                "thresholds": {
                    "min_close": MIN_CLOSE,
                    "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
                    "min_event_return": MIN_EVENT_RETURN,
                    "min_event_excess_return_vs_spy": MIN_EVENT_EXCESS_RETURN_VS_SPY,
                    "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                    "min_close_location": MIN_CLOSE_LOCATION,
                },
            }
            raw_candidates_by_day.setdefault(signal_date, []).append((rows, idx, candidate))

    selected: list[dict[str, Any]] = []
    raw_qualified_count = 0
    for signal_date, entries in raw_candidates_by_day.items():
        ranked = sorted(entries, key=lambda item: _candidate_sort_key(item[2]))
        raw_qualified_count += len(ranked)
        for rows, idx, candidate in ranked[:MAX_PAPER_TRADES_PER_DAY]:
            paper_trade = _paper_trade_from_candidate(rows, idx, candidate, cfg["end"])
            if paper_trade is None:
                rejection_counts["missing_entry_or_exit_window"] += 1
                continue
            selected.append(paper_trade)

    diagnostics = {
        "event_snapshot_days": event_snapshot_days,
        "raw_dte0_event_count": raw_event_count,
        "raw_qualified_candidate_count": raw_qualified_count,
        "selected_trade_count": len(selected),
        "selected_candidate_days": len({row["signal_date"] for row in selected}),
        "selected_unique_tickers": len({row["ticker"] for row in selected}),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "earnings_snapshot_sources_sample": dict(earnings_source_counts.most_common(5)),
        "selected_tickers": sorted({row["ticker"] for row in selected}),
        "selected_sample": selected[:10],
    }
    return selected, diagnostics


def _overlay_from_paper_trades(
    before_result: dict[str, Any],
    paper_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    pnl_by_exit_date: Counter[str] = Counter()
    overlay_days: list[dict[str, Any]] = []
    for trade in paper_trades:
        exit_date = str(trade.get("exit_date") or "")
        pnl = float(trade.get("pnl") or 0.0)
        pnl_by_exit_date[exit_date] += pnl
        overlay_days.append(
            {
                "date": exit_date,
                "ticker": trade.get("ticker"),
                "signal_date": trade.get("signal_date"),
                "entry_date": trade.get("entry_date"),
                "exit_date": exit_date,
                "pnl": _round(pnl, 2),
                "source": STEM,
            }
        )

    cumulative_overlay = 0.0
    combined_curve = []
    for day, equity in before_result.get("equity_curve") or []:
        cumulative_overlay += float(pnl_by_exit_date.get(str(day), 0.0))
        combined_curve.append((str(day), round(float(equity) + cumulative_overlay, 2)))

    return {
        "overlay_total_pnl": _round(sum(pnl_by_exit_date.values()), 2),
        "combined_equity_curve": combined_curve,
        "overlay_days": overlay_days,
        "overlay_day_count": len(overlay_days),
    }


def _load_baselines() -> OrderedDict[str, dict[str, Any]]:
    baselines: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label, path in BASELINE_FILES.items():
        result = _load_json(path)
        baselines[label] = {
            "result": result,
            "metrics": _complete_expected_value(base.overlay_helper._metrics(result)),
            "artifact": _repo_rel(path),
        }
    return baselines


def _run_windows(
    baselines: OrderedDict[str, dict[str, Any]],
    selected_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for label, cfg in base.WINDOWS.items():
        target_trades = selected_by_window.get(label, [])
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = _overlay_from_paper_trades(before_result, target_trades)
        if target_trades:
            after = _complete_expected_value(
                base.overlay_helper._metrics_with_overlay(before_result, overlay)
            )
        else:
            after = dict(before)
        raw_delta = _metric_delta(after, before)
        comparison = {
            "expected_value_score_delta": raw_delta["expected_value_score"],
            "strategy_total_pnl_delta": raw_delta["total_pnl"],
            "total_pnl_delta": raw_delta["total_pnl"],
            "max_drawdown_delta": raw_delta["max_drawdown_pct"],
            "raw_delta": raw_delta,
        }
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before_artifact": baselines[label]["artifact"],
                "before": before,
                "after": after,
                "comparison": comparison,
                "target_trade_count": len(target_trades),
                "target_trade_pnl_usd": _round(
                    sum(float(row.get("pnl", 0.0)) for row in target_trades), 2
                ),
            }
        )
    return results


def _aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in results)
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in results)
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in results)
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in results)
    max_drawdown_before = max(float(row["before"]["max_drawdown_pct"]) for row in results)
    max_drawdown_after = max(float(row["after"]["max_drawdown_pct"]) for row in results)
    min_survival_before = min(float(row["before"]["survival_rate"]) for row in results)
    min_survival_after = min(float(row["after"]["survival_rate"]) for row in results)
    trade_count_before = sum(int(row["before"].get("trade_count") or 0) for row in results)
    trade_count_after = sum(int(row["after"].get("trade_count") or 0) for row in results)
    return {
        "before": {
            "expected_value_score": _round(before_ev, 6),
            "total_pnl": _round(before_pnl, 2),
            "strategy_total_pnl": _round(before_pnl, 2),
            "max_drawdown_pct": _round(max_drawdown_before, 6),
            "min_survival_rate": _round(min_survival_before, 6),
            "trade_count": trade_count_before,
        },
        "after": {
            "expected_value_score": _round(after_ev, 6),
            "total_pnl": _round(after_pnl, 2),
            "strategy_total_pnl": _round(after_pnl, 2),
            "max_drawdown_pct": _round(max_drawdown_after, 6),
            "min_survival_rate": _round(min_survival_after, 6),
            "trade_count": trade_count_after,
        },
        "comparison": {
            "expected_value_score_delta": _round(after_ev - before_ev, 6),
            "expected_value_score_delta_pct": _round((after_ev - before_ev) / before_ev, 6)
            if before_ev
            else None,
            "strategy_total_pnl_delta": _round(after_pnl - before_pnl, 2),
            "total_pnl_delta": _round(after_pnl - before_pnl, 2),
            "strategy_total_pnl_delta_pct": _round((after_pnl - before_pnl) / before_pnl, 6)
            if before_pnl
            else None,
            "max_drawdown_pct": _round(max_drawdown_after - max_drawdown_before, 6),
            "min_survival_rate": _round(min_survival_after - min_survival_before, 6),
            "trade_count": trade_count_after - trade_count_before,
        },
    }


def _target_trade_summary(selected_by_window: OrderedDict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trades = [row for rows in selected_by_window.values() for row in rows]
    pnl_by_window = {
        label: _round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
        for label, rows in selected_by_window.items()
    }
    trades_by_window = {label: len(rows) for label, rows in selected_by_window.items()}
    ticker_pnl: Counter[str] = Counter()
    positive_ticker_pnl: Counter[str] = Counter()
    for row in all_trades:
        ticker = str(row.get("ticker") or "")
        pnl = float(row.get("pnl") or 0.0)
        ticker_pnl[ticker] += pnl
        if pnl > 0:
            positive_ticker_pnl[ticker] += pnl
    positive_total = sum(positive_ticker_pnl.values())
    if positive_total > 0:
        shares = [value / positive_total for value in positive_ticker_pnl.values()]
        max_share = max(shares)
        hhi = sum(share * share for share in shares)
    else:
        max_share = 0.0
        hhi = 0.0
    ticker_rows = []
    for ticker, pnl in ticker_pnl.most_common():
        positive = positive_ticker_pnl.get(ticker, 0.0)
        ticker_rows.append(
            {
                "ticker": ticker,
                "trade_count": sum(1 for row in all_trades if row.get("ticker") == ticker),
                "paper_pnl_usd": _round(pnl, 2),
                "positive_pnl_usd": _round(positive, 2),
                "positive_pnl_share": _round(positive / positive_total, 6)
                if positive_total
                else 0.0,
            }
        )
    return {
        "target_trade_count": len(all_trades),
        "target_trade_pnl_usd": _round(sum(float(row.get("pnl") or 0.0) for row in all_trades), 2),
        "trades_by_window": trades_by_window,
        "pnl_by_window": pnl_by_window,
        "unique_tickers": len(ticker_pnl),
        "positive_pnl_total_usd": _round(positive_total, 2),
        "max_single_positive_share": _round(max_share, 6),
        "positive_pnl_hhi": _round(hhi, 6),
        "ticker_rows": ticker_rows,
    }


def _baseline_caveat(aggregate: dict[str, Any]) -> dict[str, Any]:
    current_ev = float(aggregate["before"]["expected_value_score"])
    current_pnl = float(aggregate["before"]["total_pnl"])
    return {
        "canonical_docs_ev": CANONICAL_DOC_EV,
        "canonical_docs_pnl": CANONICAL_DOC_PNL,
        "current_replay_ev": _round(current_ev, 6),
        "current_replay_pnl": _round(current_pnl, 2),
        "ev_delta_vs_docs": _round(current_ev - CANONICAL_DOC_EV, 6),
        "pnl_delta_vs_docs": _round(current_pnl - CANONICAL_DOC_PNL, 2),
        "matches_docs": abs(current_ev - CANONICAL_DOC_EV) <= 0.001
        and abs(current_pnl - CANONICAL_DOC_PNL) <= 1.0,
    }


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = float(comparison.get("expected_value_score_delta") or 0.0)
    pnl_delta = float(comparison.get("strategy_total_pnl_delta") or 0.0)
    max_drawdown_delta = max(
        float(row["comparison"].get("max_drawdown_delta") or 0.0) for row in results
    )
    ev_windows = [
        row["label"]
        for row in results
        if float(row["comparison"].get("expected_value_score_delta") or 0.0) > 0.0
    ]
    pnl_windows = [
        row["label"]
        for row in results
        if float(row["comparison"].get("strategy_total_pnl_delta") or 0.0) > 0.0
    ]
    min_survival_rate = min(float(row["after"].get("survival_rate") or 0.0) for row in results)
    target_trade_count = int(target_summary["target_trade_count"])
    target_window_count = sum(1 for row in results if int(row["target_trade_count"]) > 0)
    concentration_passed = (
        float(target_summary["max_single_positive_share"] or 0.0) <= MAX_SINGLE_POSITIVE_SHARE
        and float(target_summary["positive_pnl_hhi"] or 0.0) <= MAX_POSITIVE_HHI
    )
    gates = OrderedDict(
        [
            ("aggregate_expected_value_positive", ev_delta > 0.0),
            ("aggregate_pnl_positive", pnl_delta > 0.0),
            ("all_windows_expected_value_improved", len(ev_windows) == len(results)),
            ("all_windows_pnl_improved", len(pnl_windows) == len(results)),
            ("target_trade_count_passed", target_trade_count >= MIN_TARGET_TRADES),
            ("target_window_count_passed", target_window_count >= MIN_TARGET_WINDOWS),
            ("drawdown_drift_passed", max_drawdown_delta <= MAX_DRAWDOWN_WORSE),
            ("survival_floor_passed", min_survival_rate >= 0.05),
            ("concentration_guard_passed", concentration_passed),
        ]
    )
    failed = [name for name, passed in gates.items() if not passed]
    alpha_passed = not failed
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter_and_forward_rows"
        if alpha_passed
        else "rejected_post_earnings_reaction_candidate_pool"
    )
    rationale = (
        "The post-earnings reaction source passed the three-window replay gate, but no shared default-off production adapter is retained in this run. Promotion requires a parity-tested adapter that consumes post_earnings_continuation_confirmed_v1 directly plus forward replacement-value rows."
        if alpha_passed
        else "Gate 4 failed, so no strategy, production, shared adapter, watchlist, or order-path change is retained."
    )
    return {
        "passed": alpha_passed,
        "alpha_passed": alpha_passed,
        "promotable_now": False,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "failed_gates": failed,
        "ev_windows_improved": ev_windows,
        "pnl_windows_improved": pnl_windows,
        "max_drawdown_delta": _round(max_drawdown_delta, 6),
        "min_survival_rate": _round(min_survival_rate, 6),
        "requires_forward_replacement_value_before_promotion": True,
        "requires_shared_adapter_before_promotion": True,
        "requires_parity_before_promotion": True,
    }


def _calibration(decision: str, aggregate: dict[str, Any], gate4: dict[str, Any], ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") or {}
    success_probability = prediction.get("success_probability")
    actual_success = 1 if gate4["alpha_passed"] else 0
    brier = None
    if isinstance(success_probability, (int, float)):
        brier = (float(success_probability) - actual_success) ** 2
    predicted_modes = prediction.get("main_failure_modes") or []
    realized_modes = list(gate4.get("failed_gates") or [])
    return {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": success_probability,
        "brier_score": _round(brier, 6),
        "expected_ev_delta": prediction.get("expected_ev_delta"),
        "actual_ev_delta": aggregate["comparison"]["expected_value_score_delta"],
        "expected_pnl_delta": prediction.get("expected_pnl_delta"),
        "actual_pnl_delta": aggregate["comparison"]["strategy_total_pnl_delta"],
        "predicted_failure_modes": predicted_modes,
        "realized_failure_mode": realized_modes,
        "predicted_failure_mode_hit": any(
            str(mode).lower() in ",".join(realized_modes).lower() for mode in predicted_modes
        ),
    }


def _update_registry(payload: dict[str, Any], now: str) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    for item in registry.get("experiments", []):
        if item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = payload["status"]
            item["completed_at"] = now
            item["decision"] = payload["decision"]
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["report_file"] = _repo_rel(ARTIFACT_MD)
            break
    registry["updated_at"] = now
    _write_json(REGISTRY_JSON, registry)


def _update_ticket(payload: dict[str, Any], now: str) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket["status"] = payload["status"]
    ticket["completed_at"] = now
    ticket["result"] = {
        "decision": payload["decision"],
        "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
            "expected_value_score_delta"
        ],
        "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
            "strategy_total_pnl_delta"
        ],
        "artifact": _repo_rel(OUT_JSON),
        "report_file": _repo_rel(ARTIFACT_MD),
    }
    _write_json(TICKET_JSON, ticket)


def _write_card(payload: dict[str, Any], now: str) -> None:
    agg = payload["aggregate"]
    text = f"""---
experiment_id: "{EXPERIMENT_ID}"
status: "{payload['status']}"
lane: "alpha_search"
change_type: "default_off_paper_candidate_pool"
mechanism_family: "default_off_paper_adapter"
trial_family: "{TRIAL_FAMILY}"
trial_variant_id: "{TRIAL_VARIANT_ID}"
changed_variable: "{CHANGED_VARIABLE}"
completed_at: "{now}"
artifact: "{_repo_rel(OUT_JSON)}"
---

# Experiment Card: {EXPERIMENT_ID}

## Summary

Tested a replay-only default-off post-earnings reaction candidate source. Decision: `{payload['decision']}`.

## Gate 4

- Aggregate EV: `{agg['before']['expected_value_score']}` -> `{agg['after']['expected_value_score']}` (`{agg['comparison']['expected_value_score_delta']:+.4f}`)
- Aggregate PnL: `${agg['before']['total_pnl']:,.2f}` -> `${agg['after']['total_pnl']:,.2f}` (`${agg['comparison']['strategy_total_pnl_delta']:,.2f}`)
- Target trades: `{payload['target_trade_summary']['target_trade_count']}`
- Failed gates: `{", ".join(payload['gate4']['failed_gates']) if payload['gate4']['failed_gates'] else "none"}`

## Repro

`.\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260602_004_post_earnings_reaction_candidate_pool.py`
"""
    _write_text(CARD_MD, text)


def _markdown_report(payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID}: Post-Earnings Reaction Candidate Pool",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Baseline: `{BASELINE_EXPERIMENT_ID}` canonical current core after artifacts",
        "- JavaScript: not used",
        "",
        "## Gate 4 Summary",
        "",
        "| Metric | Before | After | Delta |",
        "|---|---:|---:|---:|",
        (
            "| Aggregate EV | "
            f"{agg['before']['expected_value_score']:.4f} | "
            f"{agg['after']['expected_value_score']:.4f} | "
            f"{agg['comparison']['expected_value_score_delta']:+.4f} |"
        ),
        (
            "| Aggregate PnL | "
            f"${agg['before']['total_pnl']:,.2f} | "
            f"${agg['after']['total_pnl']:,.2f} | "
            f"${agg['comparison']['strategy_total_pnl_delta']:,.2f} |"
        ),
        (
            "| Max drawdown ceiling | "
            f"{agg['before']['max_drawdown_pct']:.2%} | "
            f"{agg['after']['max_drawdown_pct']:.2%} | "
            f"{agg['comparison']['max_drawdown_pct']:+.2%} |"
        ),
        (
            "| Min survival rate | "
            f"{agg['before']['min_survival_rate']:.2%} | "
            f"{agg['after']['min_survival_rate']:.2%} | "
            f"{agg['comparison']['min_survival_rate']:+.2%} |"
        ),
        "",
        "## Three Windows",
        "",
        "| Window | EV before | EV after | EV delta | PnL delta | Target trades |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["windows"]:
        lines.append(
            "| "
            f"{row['label']} | "
            f"{row['before']['expected_value_score']:.4f} | "
            f"{row['after']['expected_value_score']:.4f} | "
            f"{row['comparison']['expected_value_score_delta']:+.4f} | "
            f"${row['comparison']['strategy_total_pnl_delta']:,.2f} | "
            f"{row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Gate 2",
            "",
            f"- Open-position field audit passed: `{payload['gate2']['open_positions']['passed']}`",
            "- Runtime fields: exact-day earnings snapshot, exact OHLCV rows, SPY OHLCV rows, next-open entry, ten-trading-day close exit.",
            "",
            "## Production Parity",
            "",
            (
                "No production or shared adapter behavior changed. This replay uses "
                "the newly accepted post-earnings continuation semantics as the "
                "future adapter boundary, but keeps the result default-off and "
                "replay-only. A positive result still requires a shared adapter "
                "that consumes `post_earnings_continuation_confirmed_v1` directly."
            ),
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def _write_manifest(now: str) -> None:
    files = {
        "runner": _repo_rel(Path(__file__)),
        "result": _repo_rel(OUT_JSON),
        "before_aggregate": _repo_rel(BEFORE_JSON),
        "after_aggregate": _repo_rel(AFTER_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket": _repo_rel(TICKET_JSON),
        "card": _repo_rel(CARD_MD),
        "artifact": _repo_rel(ARTIFACT_MD),
        "baseline_late_strong": _repo_rel(BASELINE_FILES["late_strong"]),
        "baseline_mid_weak": _repo_rel(BASELINE_FILES["mid_weak"]),
        "baseline_old_thin": _repo_rel(BASELINE_FILES["old_thin"]),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": now,
        "files": {
            label: {
                "path": rel_path,
                "exists": (ROOT / rel_path).exists(),
                "sha256": _sha256(ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _build_payload(now: str) -> dict[str, Any]:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    universe = {ticker.upper() for ticker in get_universe()}
    baselines = _load_baselines()
    selected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    diagnostics_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        snapshot = _load_ohlcv_snapshot(ROOT / cfg["snapshot"])
        selected, diagnostics = _select_candidates_for_window(label, cfg, universe, snapshot)
        selected_by_window[label] = selected
        diagnostics_by_window[label] = diagnostics

    results = _run_windows(baselines, selected_by_window)
    aggregate = _aggregate_results(results)
    target_summary = _target_trade_summary(selected_by_window)
    gate4 = _gate4(aggregate, results, target_summary)
    status = "completed"
    decision = gate4["decision"]
    interpretation = (
        "The post-earnings reaction candidate source is a positive replay lead, but it is not promoted in this run. Keep it default-off until forward replacement-value rows and a shared parity-tested adapter exist."
        if gate4["alpha_passed"]
        else "The post-earnings reaction candidate source did not clear Gate 4. Do not promote it or retry nearby event-day return, close-location, or RS thresholds on these frozen windows without forward rows or a materially richer event-quality field."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": ticket.get(
            "hypothesis",
            "PIT-safe post-earnings continuation events with strong same-day price reaction and RS may add a default-off paper candidate source beyond core-selected trades.",
        ),
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": "default_off_paper_adapter",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": ticket.get("prior_trial_count", 0),
        "nearby_prior_experiments": [
            "exp-20260426-037",
            "exp-20260602-002",
            "exp-20260602-003",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_post_earnings_continuation_field",
        "parameters": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "min_close": MIN_CLOSE,
            "min_avg_dollar_volume_20": MIN_AVG_DOLLAR_VOLUME_20,
            "min_event_return": MIN_EVENT_RETURN,
            "min_event_excess_return_vs_spy": MIN_EVENT_EXCESS_RETURN_VS_SPY,
            "min_rs20_vs_spy": MIN_RS20_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "stock_excluded_tickers": sorted(STOCK_EXCLUDED_TICKERS),
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news",
                "watchlists",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "pnl_improved_windows": 3,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": "candidate_pool / entry: explicit PIT-safe post-earnings continuation plus strong same-day reaction may add default-off paper candidates beyond core-selected trades.",
            "2_history_check": {
                "exp-20260426-037": "Older post-earnings shadow had zero candidates because event snapshots lacked confirmation coverage.",
                "exp-20260602-002": "Strong observed lead for core post-earnings continuation, but needed explicit fields.",
                "exp-20260602-003": "Accepted explicit shared post_earnings_continuation_confirmed_v1 semantics; this run tests a candidate-pool source on top of that field.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": "Same docs/backtesting.md three windows; positive aggregate EV/PnL; all windows improve; sample, drawdown, survival, and concentration guards pass.",
            "5_reproducibility": ".venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260602_004_post_earnings_reaction_candidate_pool.py",
        },
        "baseline_caveat": _baseline_caveat(aggregate),
        "gate1": {
            "passed": True,
            "baseline_experiment_id": BASELINE_EXPERIMENT_ID,
            "baseline_files": {label: data["artifact"] for label, data in baselines.items()},
            "aggregate_before": aggregate["before"],
        },
        "gate2": {
            "passed": _audit_open_positions()["passed"],
            "open_positions": _audit_open_positions(),
            "runtime_fields": [
                "earnings_snapshot.days_to_earnings",
                "earnings_snapshot.eps_actual_last",
                "earnings_snapshot.eps_estimate",
                "earnings_snapshot.avg_historical_surprise_pct",
                "OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV",
                "next-open paper entry price",
                "ten-trading-day close exit price",
            ],
            "field_known_at": "event-day close before next-open paper entry",
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_after_survival_rate": aggregate["after"]["min_survival_rate"],
            "hard_floor": 0.05,
            "passed": aggregate["after"]["min_survival_rate"] >= 0.05,
            "note": "Default-off paper overlay; core signal survival is unchanged.",
        },
        "gate4": gate4,
        "aggregate": aggregate,
        "windows": results,
        "candidate_diagnostics": diagnostics_by_window,
        "target_trades_by_window": selected_by_window,
        "target_trade_summary": target_summary,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "default_off_paper_only": True,
            "trade_enabled": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "llm_or_news_changed": False,
            "promotion_requirement": "A retained result requires a shared default-off adapter that consumes post_earnings_continuation_confirmed_v1 directly and focused parity tests.",
        },
        "production_parity": {
            "alters_core_backtester": False,
            "alters_production_orders": False,
            "default_enabled": False,
            "replay_only": True,
            "parity_note": "No production code path is changed. If this source is promoted later, both run.py and backtester.py must use the accepted explicit post_earnings_continuation_confirmed_v1 field through one shared paper adapter.",
        },
        "calibration": _calibration(decision, aggregate, gate4, ticket),
        "interpretation": interpretation,
        "next_retry_requires": [
            "forward replacement-value rows",
            "shared default-off adapter using post_earnings_continuation_confirmed_v1",
            "focused production/backtest parity tests",
            "materially richer event-quality field if this source is rejected",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_JSON),
            _repo_rel(AFTER_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }
    return payload


def main() -> int:
    now = _utc_now()
    payload = _build_payload(now)

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(BEFORE_JSON, payload["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_text(ARTIFACT_MD, _markdown_report(payload))
    _write_card(payload, now)
    _update_ticket(payload, now)
    _update_registry(payload, now)
    _upsert_jsonl(
        EXPERIMENT_LOG,
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": now,
            "lane": "alpha_search",
            "status": payload["status"],
            "decision": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "changed_variable": payload["changed_variable"],
            "prior_trial_count": payload["prior_trial_count"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "parameters": payload["parameters"],
            "before_metrics": payload["aggregate"]["before"],
            "after_metrics": payload["aggregate"]["after"],
            "delta_metrics": payload["aggregate"]["comparison"],
            "gate4": payload["gate4"],
            "target_trade_summary": payload["target_trade_summary"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "rejection_reason": ";".join(payload["gate4"]["failed_gates"])
            if payload["gate4"]["failed_gates"]
            else None,
            "next_retry_requires": payload["next_retry_requires"],
            "related_files": payload["related_files"],
            "artifact": _repo_rel(OUT_JSON),
            "report_file": _repo_rel(ARTIFACT_MD),
            "anti_js": "No JavaScript was used.",
        },
    )
    _write_manifest(now)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate": payload["aggregate"],
                "gate4_failed": payload["gate4"]["failed_gates"],
                "target_trade_summary": payload["target_trade_summary"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
