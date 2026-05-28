"""exp-20260528-014: Kova sell-side lifecycle taxonomy.

This observed-only experiment explores a Kova direction that had not yet been
tested as a full taxonomy in Ginger: classifying the sell-side lifecycle of the
accepted top-2 QQQ-confirmed VCP paper trades.

It reads the accepted exp-20260526-007 VCP top-2 paper trades, joins only
post-entry OHLCV available inside the source 10-trading-day paper hold, and
reports lifecycle buckets such as stop-loss touch, support break, profit
giveback, climax/churning, and gap-down proxy. It does not change entries,
exits, ranking, sizing, paper notional, LLM/news, production watchlists, or
live/default orders.
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

EXPERIMENT_ID = "exp-20260528-014"
STEM = "kova_sell_side_lifecycle_taxonomy"
TRIAL_FAMILY = "kova_sell_side_lifecycle_taxonomy"
CHANGED_VARIABLE = "kova_sell_side_lifecycle_taxonomy_v1"
RULE_VERSION = "kova_sell_side_lifecycle_taxonomy_v1"
SOURCE_VARIANT = "rank2_125"

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

MAX_LOSS_STOP_PCT = 0.075
VOLUME_LOOKBACK_DAYS = 50
MIN_VOLUME_LOOKBACK_DAYS = 20
HIGH_VOLUME_RATIO = 1.50
CLIMAX_VOLUME_RATIO = 2.00
CLOSE_LOCATION_WEAK_MAX = 0.40
CLIMAX_CLOSE_LOCATION_MAX = 0.55
SHORT_MA_DAYS = 21
MEDIUM_MA_DAYS = 50
EVENT_GAP_DOWN_PCT = -0.05
EVENT_DOWN_DAY_PCT = -0.08
PROFIT_GIVEBACK_MIN_MFE = 0.10
PROFIT_GIVEBACK_FROM_HIGH_CLOSE = 0.07
FAILED_BREAKOUT_MAX_MFE = 0.02
FAILED_BREAKOUT_MAE = -0.04
STRONG_FOLLOWTHROUGH_PNL_PCT = 0.08
ACTIONABLE_MIN_TRADES = 10

BUCKET_PRIORITY = [
    "event_gap_down_proxy",
    "max_loss_stop_touch",
    "support_break_high_volume_weak_close",
    "profit_protection_giveback",
    "climax_or_churning",
    "failed_breakout_low_mfe",
    "strong_followthrough_no_warning",
    "orderly_or_unclassified_hold",
]


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


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
    line = json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            found = any(
                experiment_id in existing
                and json.loads(existing).get("experiment_id") == experiment_id
                for existing in handle
                if existing.strip() and existing.lstrip().startswith("{")
            )
        if not found:
            with path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(line + "\n")
        return
    else:
        path.write_text(line + "\n", encoding="utf-8")
        return


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _row_date(row: dict[str, Any]) -> str:
    return _date10(row.get("Date") if "Date" in row else row.get("date"))


def _field(row: dict[str, Any], name: str) -> float | None:
    value = row.get(name)
    if value is None:
        value = row.get(name.lower())
    return _num(value)


def _load_snapshot(path: str) -> dict[str, list[dict[str, Any]]]:
    payload = _read_json(REPO_ROOT / path)
    rows_by_ticker = payload.get("ohlcv", payload)
    if not isinstance(rows_by_ticker, dict):
        raise ValueError(f"Snapshot is not ticker keyed: {path}")
    normalized: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in rows_by_ticker.items():
        if not isinstance(rows, list):
            continue
        normalized[str(ticker).upper()] = sorted(
            [row for row in rows if isinstance(row, dict)],
            key=_row_date,
        )
    return normalized


def _find_index(rows: list[dict[str, Any]], target_date: str) -> int | None:
    for idx, row in enumerate(rows):
        if _row_date(row) == target_date:
            return idx
    return None


def _mean(values: list[float]) -> float | None:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _moving_average(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    start = idx - days + 1
    if start < 0:
        return None
    values = [
        value
        for row in rows[start : idx + 1]
        for value in [_field(row, "Close")]
        if value is not None and value > 0
    ]
    if len(values) != days:
        return None
    return _mean(values)


def _volume_ratio(rows: list[dict[str, Any]], idx: int) -> tuple[float | None, int]:
    start = max(0, idx - VOLUME_LOOKBACK_DAYS)
    prior_volumes = [
        value
        for row in rows[start:idx]
        for value in [_field(row, "Volume")]
        if value is not None and value > 0
    ]
    if len(prior_volumes) < MIN_VOLUME_LOOKBACK_DAYS:
        return None, len(prior_volumes)
    avg_volume = _mean(prior_volumes)
    volume = _field(rows[idx], "Volume")
    if avg_volume is None or avg_volume <= 0 or volume is None:
        return None, len(prior_volumes)
    return volume / avg_volume, len(prior_volumes)


def _close_location(row: dict[str, Any]) -> float | None:
    high = _field(row, "High")
    low = _field(row, "Low")
    close = _field(row, "Close")
    if high is None or low is None or close is None:
        return None
    if high <= low:
        return 0.5
    return (close - low) / (high - low)


def _range_pct(row: dict[str, Any]) -> float | None:
    high = _field(row, "High")
    low = _field(row, "Low")
    close = _field(row, "Close")
    if high is None or low is None or close is None or close <= 0:
        return None
    return (high - low) / close


def _daily_return(row: dict[str, Any], prev_close: float | None) -> float | None:
    close = _field(row, "Close")
    if close is None or close <= 0 or prev_close is None or prev_close <= 0:
        return None
    return close / prev_close - 1.0


def _open_gap(row: dict[str, Any], prev_close: float | None) -> float | None:
    open_price = _field(row, "Open")
    if open_price is None or open_price <= 0 or prev_close is None or prev_close <= 0:
        return None
    return open_price / prev_close - 1.0


def _support_break_type(close: float, ma21: float | None, ma50: float | None) -> str | None:
    below_21 = ma21 is not None and close < ma21
    below_50 = ma50 is not None and close < ma50
    if below_21 and below_50:
        return "below_21d_and_50d_ma"
    if below_50:
        return "below_50d_ma"
    if below_21:
        return "below_21d_ma"
    return None


def _load_source_trades() -> tuple[dict[str, Any], "OrderedDict[str, list[dict[str, Any]]]"]:
    source = _read_json(SOURCE_ARTIFACT)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing {SOURCE_VARIANT} in {SOURCE_ARTIFACT}")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing target_trades_by_window in {SOURCE_ARTIFACT}")
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label in WINDOWS:
        out[label] = [
            {**row, "window": label}
            for row in trades_by_window.get(label, [])
            if isinstance(row, dict)
        ]
    return source, out


def _load_ohlcv_by_window() -> dict[str, dict[str, list[dict[str, Any]]]]:
    return {
        label: _load_snapshot(cfg["snapshot"])
        for label, cfg in WINDOWS.items()
    }


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


def _set_flag(
    flags: dict[str, dict[str, Any]],
    name: str,
    date: str,
    detail: dict[str, Any],
) -> None:
    if name not in flags:
        flags[name] = {"first_date": date, "detail": detail}


def _classify_trade(
    trade: dict[str, Any],
    ohlcv_by_window: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    window = str(trade.get("window") or "")
    ticker = str(trade.get("ticker") or "").upper()
    entry_date = _date10(trade.get("entry_date"))
    exit_date = _date10(trade.get("exit_date"))
    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    entry_price = _num(trade.get("entry_price"))
    base_pnl = _num(trade.get("pnl")) or 0.0
    base_notional = _num(trade.get("paper_notional_usd")) or 0.0
    base_pnl_pct = base_pnl / base_notional if base_notional else None
    bars = ohlcv_by_window.get(window, {}).get(ticker, [])
    entry_idx = _find_index(bars, entry_date)
    exit_idx = _find_index(bars, exit_date)

    result: dict[str, Any] = {
        "window": window,
        "ticker": ticker,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "vcp_candidate_rank_on_signal_date": trade.get("vcp_candidate_rank_on_signal_date"),
        "paper_notional_usd": round(base_notional, 4),
        "base_pnl": round(base_pnl, 4),
        "base_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "taxonomy_status": "ok",
        "primary_sell_side_bucket": "orderly_or_unclassified_hold",
        "sell_side_labels": [],
        "first_warning_date": None,
        "max_high_return_pct": None,
        "max_close_return_pct": None,
        "max_adverse_intraday_pct": None,
        "final_pnl_pct": round(base_pnl_pct, 6) if base_pnl_pct is not None else None,
        "days_observed": 0,
    }
    if not bars:
        result["taxonomy_status"] = "missing_ohlcv_rows"
        result["primary_sell_side_bucket"] = "unavailable"
        return result
    if entry_idx is None or exit_idx is None or entry_price is None or entry_price <= 0:
        result["taxonomy_status"] = "missing_entry_or_exit_bar"
        result["primary_sell_side_bucket"] = "unavailable"
        return result
    if exit_idx < entry_idx:
        result["taxonomy_status"] = "exit_before_entry"
        result["primary_sell_side_bucket"] = "unavailable"
        return result

    flags: dict[str, dict[str, Any]] = {}
    max_high = entry_price
    max_close = entry_price
    high_close_before_today = entry_price
    min_low = entry_price
    first_warning_date: str | None = None
    days_observed = 0

    for idx in range(entry_idx, exit_idx + 1):
        row = bars[idx]
        date = _row_date(row)
        prev_close = _field(bars[idx - 1], "Close") if idx > 0 else None
        open_price = _field(row, "Open")
        high = _field(row, "High")
        low = _field(row, "Low")
        close = _field(row, "Close")
        if close is None or close <= 0:
            continue
        days_observed += 1
        if high is not None:
            max_high = max(max_high, high)
        if low is not None:
            min_low = min(min_low, low)
        volume_ratio, volume_lookback_count = _volume_ratio(bars, idx)
        close_location = _close_location(row)
        day_return = _daily_return(row, prev_close)
        gap_return = _open_gap(row, prev_close)
        range_pct = _range_pct(row)
        ma21 = _moving_average(bars, idx, SHORT_MA_DAYS)
        ma50 = _moving_average(bars, idx, MEDIUM_MA_DAYS)
        support_break = _support_break_type(close, ma21, ma50)

        if gap_return is not None and gap_return <= EVENT_GAP_DOWN_PCT:
            _set_flag(
                flags,
                "event_gap_down_proxy",
                date,
                {
                    "gap_return_pct": round(gap_return, 6),
                    "prev_close": round(prev_close, 4) if prev_close else None,
                    "open": round(open_price, 4) if open_price else None,
                },
            )
        if (
            day_return is not None
            and day_return <= EVENT_DOWN_DAY_PCT
            and volume_ratio is not None
            and volume_ratio >= HIGH_VOLUME_RATIO
        ):
            _set_flag(
                flags,
                "event_gap_down_proxy",
                date,
                {
                    "daily_return_pct": round(day_return, 6),
                    "volume_ratio": round(volume_ratio, 4),
                    "source": "large_down_day_high_volume_proxy",
                },
            )

        if low is not None and low <= entry_price * (1.0 - MAX_LOSS_STOP_PCT):
            _set_flag(
                flags,
                "max_loss_stop_touch",
                date,
                {
                    "low": round(low, 4),
                    "stop_price": round(entry_price * (1.0 - MAX_LOSS_STOP_PCT), 4),
                },
            )

        giveback_from_high_close = (
            high_close_before_today - close
        ) / high_close_before_today if high_close_before_today > 0 else 0.0
        close_loss_vs_entry = close / entry_price - 1.0
        if (
            volume_ratio is not None
            and volume_ratio >= HIGH_VOLUME_RATIO
            and close_location is not None
            and close_location <= CLOSE_LOCATION_WEAK_MAX
            and support_break is not None
            and (close < entry_price or giveback_from_high_close >= 0.05)
        ):
            _set_flag(
                flags,
                "support_break_high_volume_weak_close",
                date,
                {
                    "support_break": support_break,
                    "volume_ratio": round(volume_ratio, 4),
                    "volume_lookback_count": volume_lookback_count,
                    "close_location": round(close_location, 4),
                    "close_loss_vs_entry": round(close_loss_vs_entry, 6),
                    "giveback_from_high_close": round(giveback_from_high_close, 6),
                },
            )

        max_close_return_before_today = high_close_before_today / entry_price - 1.0
        if (
            max_close_return_before_today >= PROFIT_GIVEBACK_MIN_MFE
            and giveback_from_high_close >= PROFIT_GIVEBACK_FROM_HIGH_CLOSE
        ):
            _set_flag(
                flags,
                "profit_protection_giveback",
                date,
                {
                    "max_close_return_before_today": round(
                        max_close_return_before_today, 6
                    ),
                    "giveback_from_high_close": round(giveback_from_high_close, 6),
                    "close_return_pct": round(close_loss_vs_entry, 6),
                },
            )

        if (
            volume_ratio is not None
            and volume_ratio >= CLIMAX_VOLUME_RATIO
            and close_location is not None
            and close_location <= CLIMAX_CLOSE_LOCATION_MAX
            and (
                (day_return is not None and day_return >= 0.05)
                or (range_pct is not None and range_pct >= 0.08 and close > entry_price * 1.05)
            )
        ):
            _set_flag(
                flags,
                "climax_or_churning",
                date,
                {
                    "volume_ratio": round(volume_ratio, 4),
                    "close_location": round(close_location, 4),
                    "daily_return_pct": round(day_return, 6)
                    if day_return is not None
                    else None,
                    "range_pct": round(range_pct, 6) if range_pct is not None else None,
                },
            )

        max_close = max(max_close, close)
        high_close_before_today = max(high_close_before_today, close)
        if first_warning_date is None and flags:
            first_warning_date = min(row["first_date"] for row in flags.values())

    max_high_return = max_high / entry_price - 1.0
    max_close_return = max_close / entry_price - 1.0
    max_adverse = min_low / entry_price - 1.0
    if (
        "failed_breakout_low_mfe" not in flags
        and max_high_return < FAILED_BREAKOUT_MAX_MFE
        and (base_pnl_pct is not None and base_pnl_pct < 0)
        and max_adverse <= FAILED_BREAKOUT_MAE
    ):
        _set_flag(
            flags,
            "failed_breakout_low_mfe",
            entry_date,
            {
                "max_high_return_pct": round(max_high_return, 6),
                "max_adverse_intraday_pct": round(max_adverse, 6),
            },
        )

    if (
        not flags
        and base_pnl_pct is not None
        and base_pnl_pct >= STRONG_FOLLOWTHROUGH_PNL_PCT
    ):
        _set_flag(
            flags,
            "strong_followthrough_no_warning",
            exit_date,
            {"base_pnl_pct": round(base_pnl_pct, 6)},
        )

    if first_warning_date is None and flags:
        first_warning_date = min(row["first_date"] for row in flags.values())

    labels = [label for label in BUCKET_PRIORITY if label in flags]
    primary = labels[0] if labels else "orderly_or_unclassified_hold"
    result.update(
        {
            "primary_sell_side_bucket": primary,
            "sell_side_labels": labels,
            "label_details": {label: flags[label] for label in labels},
            "first_warning_date": first_warning_date,
            "max_high_return_pct": round(max_high_return, 6),
            "max_close_return_pct": round(max_close_return, 6),
            "max_adverse_intraday_pct": round(max_adverse, 6),
            "days_observed": days_observed,
        }
    )
    return result


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    pnl_values = [float(row.get("base_pnl") or 0.0) for row in rows]
    pct_values = [
        float(row["base_pnl_pct"])
        for row in rows
        if isinstance(row.get("base_pnl_pct"), (int, float))
    ]
    mfe_values = [
        float(row["max_high_return_pct"])
        for row in rows
        if isinstance(row.get("max_high_return_pct"), (int, float))
    ]
    mae_values = [
        float(row["max_adverse_intraday_pct"])
        for row in rows
        if isinstance(row.get("max_adverse_intraday_pct"), (int, float))
    ]
    return {
        "trade_count": count,
        "total_pnl": round(sum(pnl_values), 4),
        "avg_pnl": round(sum(pnl_values) / count, 4) if count else 0.0,
        "median_pnl": round(median(pnl_values), 4) if pnl_values else 0.0,
        "win_rate": round(sum(1 for value in pnl_values if value > 0) / count, 6)
        if count
        else 0.0,
        "avg_pnl_pct": round(sum(pct_values) / len(pct_values), 6)
        if pct_values
        else None,
        "avg_mfe_high_pct": round(sum(mfe_values) / len(mfe_values), 6)
        if mfe_values
        else None,
        "avg_mae_low_pct": round(sum(mae_values) / len(mae_values), 6)
        if mae_values
        else None,
    }


def _bucket_summary(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    out: dict[str, Any] = OrderedDict()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    for bucket in sorted(grouped, key=lambda b: (-len(grouped[b]), b)):
        out[bucket] = _summarize(grouped[bucket])
    return out


def _label_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        labels = row.get("sell_side_labels")
        if not labels:
            grouped["no_sell_side_label"].append(row)
            continue
        for label in labels:
            grouped[str(label)].append(row)
    return {
        label: _summarize(grouped[label])
        for label in sorted(grouped, key=lambda b: (-len(grouped[b]), b))
    }


def _window_bucket_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = OrderedDict()
    for label in WINDOWS:
        subset = [row for row in rows if row.get("window") == label]
        out[label] = _bucket_summary(subset, "primary_sell_side_bucket")
    return out


def _rest_summary(rows: list[dict[str, Any]], bucket: str) -> dict[str, Any]:
    return _summarize([row for row in rows if row.get("primary_sell_side_bucket") != bucket])


def _actionability_probe(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for bucket, stats in summary.items():
        if bucket in {"unavailable", "orderly_or_unclassified_hold"}:
            continue
        bucket_rows = [
            row for row in rows if row.get("primary_sell_side_bucket") == bucket
        ]
        rest = _rest_summary(rows, bucket)
        avg_pnl = float(stats.get("avg_pnl") or 0.0)
        rest_avg_pnl = float(rest.get("avg_pnl") or 0.0)
        candidates.append(
            {
                "bucket": bucket,
                "trade_count": stats.get("trade_count"),
                "total_pnl": stats.get("total_pnl"),
                "avg_pnl": stats.get("avg_pnl"),
                "rest_avg_pnl": rest.get("avg_pnl"),
                "avg_pnl_delta_vs_rest": round(avg_pnl - rest_avg_pnl, 4),
                "meets_min_sample": int(stats.get("trade_count") or 0)
                >= ACTIONABLE_MIN_TRADES,
                "negative_total_pnl": float(stats.get("total_pnl") or 0.0) < 0.0,
            }
        )
    actionable = [
        row
        for row in candidates
        if row["meets_min_sample"] and row["negative_total_pnl"]
    ]
    weak_but_positive = [
        row
        for row in candidates
        if row["meets_min_sample"]
        and not row["negative_total_pnl"]
        and row["avg_pnl_delta_vs_rest"] < 0
    ]
    if actionable:
        gate_status = "observed_taxonomy_has_negative_candidate_bucket"
        reason = (
            "At least one lifecycle bucket has >=10 trades and negative total PnL; "
            "this can only justify a later shared lifecycle replay, not a rule now."
        )
    elif weak_but_positive:
        gate_status = "observed_only_context_not_promotable"
        reason = (
            "Some lifecycle buckets underperform the rest, but none with enough "
            "sample has negative total PnL under the source exits."
        )
    else:
        gate_status = "observed_only_no_actionable_sell_side_bucket"
        reason = (
            "No sell-side bucket has both enough sample and negative realized PnL."
        )
    return {
        "gate_status": gate_status,
        "reason": reason,
        "minimum_actionable_trades": ACTIONABLE_MIN_TRADES,
        "candidate_buckets": sorted(candidates, key=lambda r: r["avg_pnl_delta_vs_rest"]),
        "actionable_negative_buckets": actionable,
        "weak_but_positive_buckets": weak_but_positive,
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# {EXPERIMENT_ID} Kova Sell-Side Lifecycle Taxonomy",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "This is observed-only attribution on the accepted exp-20260526-007 VCP "
        "top-2 paper trades. It does not alter entries, exits, ranking, sizing, "
        "paper notional, LLM/news, production watchlists, or orders.",
        "",
        "## Gate Questions",
        "",
    ]
    for key, value in payload["gate_questions"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Coverage",
            "",
            f"- Target trades: `{payload['coverage']['target_trade_count']}`",
            f"- Classified trades: `{payload['coverage']['classified_trade_count']}`",
            f"- Missing / unavailable rows: `{payload['coverage']['unavailable_trade_count']}`",
            "",
            "## Primary Bucket Summary",
            "",
            "| Bucket | Trades | PnL | Avg PnL | Win Rate | Avg MFE | Avg MAE |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for bucket, stats in payload["primary_bucket_summary"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    bucket,
                    str(stats["trade_count"]),
                    f"{stats['total_pnl']:.2f}",
                    f"{stats['avg_pnl']:.2f}",
                    f"{stats['win_rate']:.2%}",
                    f"{stats['avg_mfe_high_pct']:.2%}"
                    if stats["avg_mfe_high_pct"] is not None
                    else "",
                    f"{stats['avg_mae_low_pct']:.2%}"
                    if stats["avg_mae_low_pct"] is not None
                    else "",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Multi-Label Summary",
            "",
            "| Label | Trades | PnL | Avg PnL | Win Rate |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for label, stats in payload["label_summary"].items():
        lines.append(
            f"| {label} | {stats['trade_count']} | {stats['total_pnl']:.2f} | "
            f"{stats['avg_pnl']:.2f} | {stats['win_rate']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Actionability Probe",
            "",
            f"- Gate status: `{payload['actionability_probe']['gate_status']}`",
            f"- Reason: {payload['actionability_probe']['reason']}",
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    source, trades_by_window = _load_source_trades()
    ohlcv_by_window = _load_ohlcv_by_window()
    rows: list[dict[str, Any]] = []
    for label in WINDOWS:
        for trade in trades_by_window.get(label, []):
            rows.append(_classify_trade(trade, ohlcv_by_window))

    target_count = sum(len(trades_by_window[label]) for label in WINDOWS)
    unavailable_count = sum(
        1 for row in rows if row.get("primary_sell_side_bucket") == "unavailable"
    )
    primary_summary = _bucket_summary(rows, "primary_sell_side_bucket")
    label_summary = _label_summary(rows)
    actionability = _actionability_probe(rows, primary_summary)
    label_counts = Counter(
        label
        for row in rows
        for label in (row.get("sell_side_labels") or ["no_sell_side_label"])
    )
    top_underperformers = actionability["candidate_buckets"][:5]

    if actionability["actionable_negative_buckets"]:
        decision = "observed_only_taxonomy_candidate_for_later_lifecycle_replay"
        interpretation = (
            "The taxonomy found at least one sufficiently populated negative-PnL "
            "sell-side bucket. This is not an exit rule; the only valid next step "
            "would be a separate shared lifecycle replay with replacement-value, "
            "drawdown, survival, and production/backtest parity accounting."
        )
    else:
        decision = "observed_only_kova_sell_side_taxonomy_context"
        interpretation = (
            "The full Kova sell-side taxonomy is useful context, but this frozen "
            "VCP sample does not justify promoting a sell-side rule. Single exit "
            "rules have already failed nearby tests, and this taxonomy should be "
            "used to design a later lifecycle replay only if forward rows or a "
            "clearly negative bucket mature."
        )

    timestamp = _now()
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "observed_only",
        "lane": "alpha_search",
        "decision": decision,
        "hypothesis": (
            "Kova's full sell-side lifecycle may reveal whether accepted VCP top-2 "
            "paper trades fail through distinct stop-loss, support-break, "
            "profit-giveback, climax/churning, or event-gap pathways."
        ),
        "change_summary": (
            "Added an observed-only post-entry sell-side lifecycle taxonomy for "
            "accepted VCP top-2 paper trades; no trading behavior changed."
        ),
        "change_type": "observed_only_attribution",
        "mechanism_family": "kova_sell_side_lifecycle",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260527-016",
            "exp-20260527-910",
            "exp-20260527-909",
            "exp-20260528-002",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "closed_vcp_trade_lifecycle_taxonomy",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "source_variant": SOURCE_VARIANT,
            "rule_version": RULE_VERSION,
            "max_loss_stop_pct": MAX_LOSS_STOP_PCT,
            "high_volume_ratio": HIGH_VOLUME_RATIO,
            "climax_volume_ratio": CLIMAX_VOLUME_RATIO,
            "event_gap_down_pct": EVENT_GAP_DOWN_PCT,
            "profit_giveback_min_mfe": PROFIT_GIVEBACK_MIN_MFE,
            "profit_giveback_from_high_close": PROFIT_GIVEBACK_FROM_HIGH_CLOSE,
            "failed_breakout_max_mfe": FAILED_BREAKOUT_MAX_MFE,
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
            "snapshot": WINDOWS["late_strong"]["snapshot"],
        },
        "secondary_windows": [
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
            }
            for label, cfg in WINDOWS.items()
            if label != "late_strong"
        ],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit / lifecycle attribution: classify accepted VCP paper trades "
                "by Kova sell-side failure or profit-protection pathway."
            ),
            "1_playbook_alignment": (
                "Matches the Kova recommended next work: sell-side observed-only "
                "taxonomy before any executable lifecycle policy."
            ),
            "2_history_check": (
                "Nearby single-variable Kova exit/pyramid tests were rejected or "
                "insufficient: entry-day-low stop, fixed max-loss stop, pyramid, "
                "and high-volume weak-close support-break exit. No full taxonomy "
                "had been logged."
            ),
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Observed-only: taxonomy can only nominate a later Gate 1-4 shared "
                "lifecycle replay. It cannot promote an exit unless a separate "
                "strategy experiment passes docs/backtesting.md."
            ),
            "5_reproducibility": (
                f"Script, source artifact, JSON output, ticket, log, and markdown "
                f"artifact are written under {EXPERIMENT_ID}."
            ),
        },
        "gate1": {
            "baseline_artifact": _repo_rel(SOURCE_ARTIFACT),
            "baseline_decision": source.get("decision"),
            "standard_windows": WINDOWS,
        },
        "gate2": {
            "required_fields": [
                "source trade entry_date",
                "source trade exit_date",
                "source trade entry_price",
                "source trade paper_notional_usd",
                "post-entry OHLCV Open/High/Low/Close/Volume",
            ],
            "operator_open_positions_audit": _audit_open_positions(),
        },
        "gate3": {
            "source_signals_survived": 117,
            "source_survival_rate": 1.0,
            "new_filter_added": False,
            "note": "No candidate is filtered; this is taxonomy only.",
        },
        "gate4": {
            "strategy_behavior_changed": False,
            "canonical_backtest_required": False,
            "result": actionability["gate_status"],
            "note": actionability["reason"],
        },
        "coverage": {
            "target_trade_count": target_count,
            "classified_trade_count": len(rows) - unavailable_count,
            "unavailable_trade_count": unavailable_count,
            "by_window": {
                label: {
                    "target_trades": len(trades_by_window[label]),
                    "classified_trades": sum(
                        1
                        for row in rows
                        if row.get("window") == label
                        and row.get("primary_sell_side_bucket") != "unavailable"
                    ),
                }
                for label in WINDOWS
            },
        },
        "before_metrics": {
            "target_trade_summary": source.get("profile_results", {})
            .get(SOURCE_VARIANT, {})
            .get("target_trade_summary"),
        },
        "after_metrics": {
            "primary_bucket_summary": primary_summary,
            "label_summary": label_summary,
            "label_counts": dict(label_counts),
        },
        "delta_metrics": {
            "strategy_delta": 0.0,
            "paper_pnl_delta": 0.0,
            "trade_count_delta": 0,
        },
        "primary_bucket_summary": primary_summary,
        "label_summary": label_summary,
        "window_bucket_summary": _window_bucket_summary(rows),
        "actionability_probe": actionability,
        "top_underperforming_candidate_buckets": top_underperformers,
        "classified_trades": rows,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
            "live_slots_changed": False,
            "live_orders_changed": False,
        },
        "interpretation": interpretation,
        "rejection_reason": (
            "Observed-only taxonomy; no exit, gate, scalar, or lifecycle policy "
            "is promoted from this run."
        ),
        "next_retry_requires": [
            "A separate shared lifecycle replay if a taxonomy bucket is used for an exit.",
            "Forward VCP replacement-value rows by lifecycle bucket.",
            "Production-visible event/earnings dates before treating gap-down proxy as earnings semantics.",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(SOURCE_ARTIFACT),
        ],
    }

    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "lane": "alpha_search",
        "owner": "codex-kova",
        "hypothesis": payload["hypothesis"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "acceptance_rule": (
            "Observed-only taxonomy. No trading behavior may change unless a "
            "later shared lifecycle replay passes Gate 1-4."
        ),
        "outputs": {
            "data": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "artifact": _repo_rel(ARTIFACT_MD),
        },
        "decision": decision,
        "summary": interpretation,
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_text(ARTIFACT_MD, _markdown(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": decision}, indent=2))
    print(json.dumps(payload["coverage"], indent=2))
    print(json.dumps(payload["primary_bucket_summary"], indent=2))
    print(json.dumps(payload["actionability_probe"], indent=2))


if __name__ == "__main__":
    main()
