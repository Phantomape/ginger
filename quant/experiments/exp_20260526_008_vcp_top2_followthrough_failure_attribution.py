"""exp-20260526-008: VCP top-2 follow-through failure attribution.

This Kova-inspired attribution reads the accepted exp-20260525-037 VCP top-2
paper sleeve and asks whether early post-entry behavior explains the sleeve's
tail drag. The single observed variable is the first-three-session
``post_entry_follow_through_status_3d`` after the paper entry.

It is deliberately not an entry rule, exit rule, sizing rule, rank rule, or
production adapter change. The field is known only after the position has
already been entered, so results here can only motivate a later audited exit or
risk experiment.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260526-008"
STEM = "vcp_top2_followthrough_failure_attribution"
TRIAL_FAMILY = "volatility_contraction_top2_post_entry_followthrough_attribution"
CHANGED_VARIABLE = "post_entry_follow_through_status_3d"
RULE_VERSION = "vcp_top2_post_entry_followthrough_failure_attribution_v1"

SOURCE_EXP037_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260525-037"
    / "volatility_contraction_topn_candidate_expansion.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
EXPERIMENT_REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

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

STATUS_FAILED = "failed_below_pivot_3d"
STATUS_ADVANCED = "advanced_above_signal_close_3d"
STATUS_HELD = "held_pivot_without_advance_3d"
STATUS_UNAVAILABLE = "unavailable"
STATUS_ORDER = [STATUS_FAILED, STATUS_ADVANCED, STATUS_HELD, STATUS_UNAVAILABLE]


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


def _upsert_jsonl(path: Path, payload: dict[str, Any]) -> None:
    experiment_id = str(payload.get("experiment_id") or EXPERIMENT_ID)
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
            if row.get("experiment_id") == experiment_id:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(existing)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _date10(value: Any) -> str:
    return str(value or "")[:10]


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


def _row_value(row: dict[str, Any], field: str) -> float | None:
    return _num(row.get(field) if field in row else row.get(field.lower()))


def _row_date(row: dict[str, Any]) -> str:
    return _date10(row.get("Date") if "Date" in row else row.get("date"))


def _load_snapshot(path: str) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(REPO_ROOT / path)
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


def infer_breakout_pivot_level(trade: dict[str, Any]) -> tuple[float | None, str]:
    signal_close = _num(trade.get("close") if "close" in trade else trade.get("Close"))
    breakout_pct = _num(trade.get("breakout_above_prior_20d_high_pct"))
    if signal_close is None or signal_close <= 0:
        return None, "missing_signal_close"
    if breakout_pct is not None and breakout_pct > -0.99:
        return signal_close / (1.0 + breakout_pct), (
            "inferred_prior_20d_high_from_breakout_above_prior_20d_high_pct"
        )
    return signal_close, "signal_close_fallback_missing_breakout_pct"


def _unavailable_context(
    *,
    reason: str,
    trade: dict[str, Any],
    pivot_level: float | None = None,
    pivot_source: str | None = None,
    available_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = available_rows or []
    return {
        "post_entry_follow_through_rule_version": RULE_VERSION,
        "post_entry_follow_through_status_3d": STATUS_UNAVAILABLE,
        "post_entry_follow_through_available": False,
        "post_entry_follow_through_unavailable_reason": reason,
        "post_entry_follow_through_known_at": (
            "after_entry_plus_3_trading_day_close_attribution_only"
        ),
        "post_entry_follow_through_alters_orders": False,
        "post_entry_follow_through_trade_enabled": False,
        "breakout_pivot_level": _round(pivot_level, 4),
        "breakout_pivot_source": pivot_source,
        "signal_close": _round(
            _num(trade.get("close") if "close" in trade else trade.get("Close")),
            4,
        ),
        "entry_date": _date10(trade.get("entry_date")),
        "observed_dates_3d": [_row_date(row) for row in rows],
        "observed_close_count_3d": len(rows),
    }


def compute_post_entry_follow_through_context(
    rows: list[dict[str, Any]],
    trade: dict[str, Any],
    *,
    trading_days: int = 3,
) -> dict[str, Any]:
    """Classify first-three-session behavior after a paper entry.

    The breakout pivot is inferred from the exp037 trade's signal close and
    breakout-above-prior-20d-high percentage. Equal closes at the pivot are not
    failures; only a strict close below pivot marks ``failed_below_pivot_3d``.
    """

    entry_date = _date10(trade.get("entry_date"))
    signal_close = _num(trade.get("close") if "close" in trade else trade.get("Close"))
    entry_price = _num(trade.get("entry_price"))
    pivot_level, pivot_source = infer_breakout_pivot_level(trade)

    if not entry_date:
        return _unavailable_context(
            reason="missing_entry_date",
            trade=trade,
            pivot_level=pivot_level,
            pivot_source=pivot_source,
        )
    if pivot_level is None or signal_close is None:
        return _unavailable_context(
            reason="missing_pivot_or_signal_close",
            trade=trade,
            pivot_level=pivot_level,
            pivot_source=pivot_source,
        )
    if not rows:
        return _unavailable_context(
            reason="missing_ticker_ohlcv_rows",
            trade=trade,
            pivot_level=pivot_level,
            pivot_source=pivot_source,
        )

    sorted_rows = sorted(rows, key=_row_date)
    first_rows = [row for row in sorted_rows if _row_date(row) >= entry_date][:trading_days]
    if len(first_rows) < trading_days:
        return _unavailable_context(
            reason="fewer_than_3_entry_or_post_entry_rows",
            trade=trade,
            pivot_level=pivot_level,
            pivot_source=pivot_source,
            available_rows=first_rows,
        )

    closes = [_row_value(row, "Close") for row in first_rows]
    if any(value is None for value in closes):
        return _unavailable_context(
            reason="missing_close_in_3d_window",
            trade=trade,
            pivot_level=pivot_level,
            pivot_source=pivot_source,
            available_rows=first_rows,
        )
    close_values = [float(value) for value in closes if value is not None]
    dates = [_row_date(row) for row in first_rows]
    failed_pairs = [
        (date, close)
        for date, close in zip(dates, close_values)
        if close < pivot_level
    ]

    if failed_pairs:
        status = STATUS_FAILED
    elif close_values[-1] > signal_close:
        status = STATUS_ADVANCED
    else:
        status = STATUS_HELD

    min_close = min(close_values)
    max_close = max(close_values)
    last_close = close_values[-1]
    return {
        "post_entry_follow_through_rule_version": RULE_VERSION,
        "post_entry_follow_through_status_3d": status,
        "post_entry_follow_through_available": True,
        "post_entry_follow_through_unavailable_reason": None,
        "post_entry_follow_through_known_at": (
            "after_entry_plus_3_trading_day_close_attribution_only"
        ),
        "post_entry_follow_through_alters_orders": False,
        "post_entry_follow_through_trade_enabled": False,
        "breakout_pivot_level": _round(pivot_level, 4),
        "breakout_pivot_source": pivot_source,
        "signal_close": _round(signal_close, 4),
        "entry_date": entry_date,
        "observed_dates_3d": dates,
        "observed_closes_3d": [_round(value, 4) for value in close_values],
        "observed_close_count_3d": len(close_values),
        "first_failed_below_pivot_date_3d": failed_pairs[0][0] if failed_pairs else None,
        "first_failed_below_pivot_close_3d": _round(failed_pairs[0][1], 4)
        if failed_pairs
        else None,
        "post_entry_3d_min_close": _round(min_close, 4),
        "post_entry_3d_max_close": _round(max_close, 4),
        "post_entry_3d_last_close": _round(last_close, 4),
        "post_entry_3d_min_close_vs_pivot_pct": _round(min_close / pivot_level - 1.0, 6),
        "post_entry_3d_last_close_vs_pivot_pct": _round(last_close / pivot_level - 1.0, 6),
        "post_entry_3d_last_close_vs_signal_close_pct": _round(
            last_close / signal_close - 1.0,
            6,
        ),
        "post_entry_3d_close_return_from_entry": _round(
            last_close / entry_price - 1.0,
            6,
        )
        if entry_price
        else None,
    }


def _audit_open_positions() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "passed": False,
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "reason": "missing_open_positions_json",
        }
    payload = _load_json(OPEN_POSITIONS_JSON)
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


def _pct_sample(rows: list[dict[str, Any]], field: str) -> list[float]:
    return [
        float(value)
        for row in rows
        for value in [_num(row.get(field))]
        if value is not None
    ]


def _trade_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [float(row.get("pnl") or 0.0) for row in rows]
    pnl_pct_values = _pct_sample(rows, "pnl_pct_net")
    by_ticker_pnl: Counter[str] = Counter()
    by_window_count: Counter[str] = Counter()
    by_rank_count: Counter[str] = Counter()
    for row, pnl in zip(rows, pnl_values):
        by_ticker_pnl[str(row.get("ticker") or "").upper()] += pnl
        by_window_count[str(row.get("window") or "")] += 1
        by_rank_count[str(row.get("vcp_candidate_rank_on_signal_date") or "")] += 1
    positive_by_ticker = {
        ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0
    }
    positive_total = sum(positive_by_ticker.values())
    return {
        "trade_count": len(rows),
        "total_pnl": _round(sum(pnl_values), 2),
        "avg_pnl": _round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None,
        "win_rate": _round(
            sum(1 for value in pnl_values if value > 0) / len(pnl_values),
            6,
        )
        if pnl_values
        else None,
        "avg_pnl_pct_net": _round(
            sum(pnl_pct_values) / len(pnl_pct_values),
            6,
        )
        if pnl_pct_values
        else None,
        "by_window_count": dict(sorted(by_window_count.items())),
        "by_rank_count": dict(sorted(by_rank_count.items())),
        "by_ticker_pnl": {
            ticker: _round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "positive_by_ticker_pnl": {
            ticker: _round(pnl, 2)
            for ticker, pnl in sorted(positive_by_ticker.items())
        },
        "max_single_positive_pnl_share": _round(
            max(positive_by_ticker.values()) / positive_total,
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "positive_pnl_hhi": _round(
            sum((pnl / positive_total) ** 2 for pnl in positive_by_ticker.values()),
            6,
        )
        if positive_total > 0 and positive_by_ticker
        else None,
        "worst_trades": _trade_samples(sorted(rows, key=lambda row: row.get("pnl") or 0.0)[:5]),
        "best_trades": _trade_samples(
            sorted(rows, key=lambda row: row.get("pnl") or 0.0, reverse=True)[:5]
        ),
    }


def _trade_samples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "window": row.get("window"),
                "ticker": row.get("ticker"),
                "signal_date": row.get("signal_date") or row.get("date"),
                "entry_date": row.get("entry_date"),
                "exit_date": row.get("exit_date"),
                "rank": row.get("vcp_candidate_rank_on_signal_date"),
                "status": row.get("post_entry_follow_through_status_3d"),
                "pnl": _round(row.get("pnl"), 2),
                "pnl_pct_net": _round(row.get("pnl_pct_net"), 6),
                "breakout_pivot_level": row.get("breakout_pivot_level"),
                "observed_dates_3d": row.get("observed_dates_3d"),
                "observed_closes_3d": row.get("observed_closes_3d"),
                "post_entry_3d_min_close_vs_pivot_pct": row.get(
                    "post_entry_3d_min_close_vs_pivot_pct"
                ),
                "post_entry_3d_last_close_vs_signal_close_pct": row.get(
                    "post_entry_3d_last_close_vs_signal_close_pct"
                ),
            }
        )
    return out


def _group_by_status(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("post_entry_follow_through_status_3d") or STATUS_UNAVAILABLE)].append(
            row
        )
    return OrderedDict((status, _trade_summary(grouped.get(status, []))) for status in STATUS_ORDER)


def _group_by_window_status(
    rows_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    out: "OrderedDict[str, Any]" = OrderedDict()
    for label in WINDOWS:
        rows = rows_by_window.get(label, [])
        out[label] = {
            "all_top2_trades": _trade_summary(rows),
            "by_status": _group_by_status(rows),
        }
    return out


def _group_by_rank_status(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = sorted(
        {
            str(row.get("vcp_candidate_rank_on_signal_date") or "")
            for row in rows
            if row.get("vcp_candidate_rank_on_signal_date") not in (None, "")
        },
        key=lambda value: int(value),
    )
    return OrderedDict(
        (
            rank,
            _group_by_status(
                [row for row in rows if str(row.get("vcp_candidate_rank_on_signal_date")) == rank]
            ),
        )
        for rank in ranks
    )


def _load_source_top2() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP037_JSON)
    variant = (
        source.get("variant_results", {})
        .get("top2_equal_notional")
    )
    if not isinstance(variant, dict):
        raise ValueError("Missing exp037 top2_equal_notional variant")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError("Missing exp037 top2 target_trades_by_window")
    return {"source": source, "top2": variant, "target_trades_by_window": trades_by_window}


def _enrich_trades(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label, cfg in WINDOWS.items():
        snapshot = _load_snapshot(cfg["snapshot"])
        source_rows = source["target_trades_by_window"].get(label, [])
        enriched: list[dict[str, Any]] = []
        for trade in source_rows:
            ticker = str(trade.get("ticker") or "").upper()
            context = compute_post_entry_follow_through_context(
                snapshot.get(ticker, []),
                trade,
            )
            enriched.append({**trade, "window": label, **context})
        out[label] = enriched
    return out


def _flatten(rows_by_window: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for rows in rows_by_window.values() for row in rows]


def _counterfactual_without_failed_bucket(
    source_top2: dict[str, Any],
    rows_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Non-tradable diagnostic: removes known failed bucket after the fact."""

    by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label in WINDOWS:
        rows = rows_by_window.get(label, [])
        failed_pnl = sum(
            float(row.get("pnl") or 0.0)
            for row in rows
            if row.get("post_entry_follow_through_status_3d") == STATUS_FAILED
        )
        all_pnl = sum(float(row.get("pnl") or 0.0) for row in rows)
        by_window[label] = {
            "source_top2_pnl": _round(all_pnl, 2),
            "failed_bucket_pnl_removed": _round(failed_pnl, 2),
            "remaining_pnl_after_removing_failed_bucket": _round(all_pnl - failed_pnl, 2),
            "failed_bucket_trade_count": sum(
                1
                for row in rows
                if row.get("post_entry_follow_through_status_3d") == STATUS_FAILED
            ),
            "note": (
                "This is after-the-fact attribution only. It is not tradable as an "
                "entry filter because the failed bucket is known after entry."
            ),
        }
    total_failed = sum(row["failed_bucket_pnl_removed"] for row in by_window.values())
    total_source = sum(row["source_top2_pnl"] for row in by_window.values())
    return {
        "non_tradable": True,
        "source_exp037_top2_total_pnl": _round(total_source, 2),
        "failed_bucket_total_pnl_removed": _round(total_failed, 2),
        "remaining_pnl_after_removing_failed_bucket": _round(total_source - total_failed, 2),
        "by_window": by_window,
        "source_exp037_top2_expected_value_delta_vs_core": source_top2.get(
            "expected_value_score_delta"
        ),
        "interpretation": (
            "Useful only as a diagnostic for whether a later PIT-safe exit overlay "
            "deserves testing."
        ),
    }


def _decision(
    *,
    by_status: dict[str, Any],
    by_window_status: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    failed = by_status[STATUS_FAILED]
    advanced = by_status[STATUS_ADVANCED]
    held = by_status[STATUS_HELD]
    failed_pnls_by_window = {
        label: by_window_status[label]["by_status"][STATUS_FAILED]["total_pnl"]
        for label in WINDOWS
    }
    failed_windows_negative = [
        label for label, pnl in failed_pnls_by_window.items() if pnl is not None and pnl < 0
    ]
    failed_avg = failed["avg_pnl"]
    nonfailed_counts = advanced["trade_count"] + held["trade_count"]
    nonfailed_pnl = float(advanced["total_pnl"] or 0.0) + float(held["total_pnl"] or 0.0)
    nonfailed_avg = nonfailed_pnl / nonfailed_counts if nonfailed_counts else None
    promising = (
        failed["trade_count"] >= 20
        and failed["total_pnl"] is not None
        and failed["total_pnl"] < 0
        and len(failed_windows_negative) >= 2
        and nonfailed_avg is not None
        and failed_avg is not None
        and failed_avg < nonfailed_avg
    )
    if promising:
        return (
            "observed_only_promising_followthrough_failure_attribution",
            (
                "The post-entry failed-below-pivot bucket is large enough and worse "
                "than non-failed trades, so the next valid Kova branch is a separate "
                "PIT-safe exit/risk experiment rather than another entry filter."
            ),
            {
                "failed_bucket_trade_count_min_20": True,
                "failed_bucket_negative_aggregate": True,
                "failed_bucket_negative_windows": failed_windows_negative,
                "failed_avg_pnl": _round(failed_avg, 2),
                "nonfailed_avg_pnl": _round(nonfailed_avg, 2),
            },
        )
    return (
        "observed_only_no_actionable_followthrough_split",
        (
            "The first-three-session follow-through split did not produce a stable "
            "promotable bucket. Keep exp037 unchanged and avoid adding another "
            "post-entry rule on this frozen sample."
        ),
        {
            "failed_bucket_trade_count_min_20": failed["trade_count"] >= 20,
            "failed_bucket_negative_aggregate": failed["total_pnl"] is not None
            and failed["total_pnl"] < 0,
            "failed_bucket_negative_windows": failed_windows_negative,
            "failed_avg_pnl": _round(failed_avg, 2),
            "nonfailed_avg_pnl": _round(nonfailed_avg, 2)
            if nonfailed_avg is not None
            else None,
        },
    )


def _build_payload() -> dict[str, Any]:
    source = _load_source_top2()
    rows_by_window = _enrich_trades(source)
    all_rows = _flatten(rows_by_window)
    by_status = _group_by_status(all_rows)
    by_window_status = _group_by_window_status(rows_by_window)
    by_rank_status = _group_by_rank_status(all_rows)
    decision, interpretation, decision_evidence = _decision(
        by_status=by_status,
        by_window_status=by_window_status,
    )

    top2 = source["top2"]
    source_trade_count = sum(len(rows) for rows in source["target_trades_by_window"].values())
    enriched_trade_count = len(all_rows)
    status_counts = {
        status: by_status[status]["trade_count"]
        for status in STATUS_ORDER
        if by_status[status]["trade_count"]
    }

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": decision,
        "created_at": _now(),
        "lane": "alpha_search",
        "registry_lane": "alpha_discovery",
        "trial_family": TRIAL_FAMILY,
        "changed_variable": CHANGED_VARIABLE,
        "rule_version": RULE_VERSION,
        "summary": interpretation,
        "alpha_hypothesis": (
            "Kova-style VCP top-2 breakouts may separate after entry: trades that "
            "close back below the inferred breakout pivot during the first three "
            "entry/post-entry sessions should explain more tail drag than trades "
            "that hold or advance."
        ),
        "history_check": {
            "exp-20260525-022": (
                "Accepted QQQ-confirmed VCP top-1 paper sleeve; source baseline for "
                "the VCP paper family."
            ),
            "exp-20260525-027": (
                "Prior pocket-pivot support gate was rejected versus exp022; do not "
                "retry pocket-pivot entry support on this sample."
            ),
            "exp-20260525-030": (
                "Event context attribution was useful versus core but weaker than "
                "exp022; not a replacement rule."
            ),
            "exp-20260525-033": (
                "Dossier/catalyst attribution did not show catalyst quality as the "
                "winning VCP split."
            ),
            "exp-20260525-036": (
                "Late_strong VCP weakness was mostly underparticipation/rank-depth "
                "scarcity rather than QQQ gate decay."
            ),
            "exp-20260525-037": (
                "Accepted default-off top-2 VCP paper expansion; this experiment "
                "uses its selected trades as the source population."
            ),
            "exp-20260526-007": (
                "Rank-notional profile on top of exp037; this run is a separate "
                "post-entry attribution and does not retune capital allocation."
            ),
        },
        "single_causal_variable": {
            "name": CHANGED_VARIABLE,
            "statuses": STATUS_ORDER,
            "pivot_definition": (
                "breakout pivot inferred as signal close divided by "
                "1 + breakout_above_prior_20d_high_pct from exp037"
            ),
            "failure_definition": (
                "any close in the entry-date-inclusive first three trading sessions "
                "strictly below the inferred breakout pivot"
            ),
            "advance_definition": (
                "no pivot failure and the third observed close is above the signal "
                "close"
            ),
            "held_definition": (
                "no pivot failure but the third observed close is not above the "
                "signal close"
            ),
            "known_at": "after_entry_plus_3_trading_day_close_attribution_only",
        },
        "acceptance_standard": {
            "promotion_allowed_in_this_experiment": False,
            "reason": (
                "The tested field is known after entry, so this run can only support "
                "or reject a follow-on exit/risk experiment."
            ),
            "promising_attribution_gate": (
                "failed bucket has >=20 trades, negative aggregate PnL, negative "
                "PnL in at least two windows, and worse average PnL than non-failed "
                "trades"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP037_JSON),
            "source_variant": "top2_equal_notional",
            "paper_entry": "next available open from exp037",
            "paper_exit": "10 trading days after signal from exp037",
            "paper_notional_usd": 10_000.0,
            "changed_core_logic": False,
        },
        "gate1": {
            "passed": True,
            "baseline_core_stack": "exp-20260517-009 accepted core stack",
            "source_paper_baseline": "exp-20260525-037 top2_equal_notional",
            "source_exp037_summary": {
                "expected_value_score_delta_vs_core": top2.get(
                    "expected_value_score_delta"
                ),
                "total_pnl_delta_vs_core": top2.get("total_pnl_delta"),
                "target_trade_count": source_trade_count,
                "source_exp022_comparison": top2.get("source_exp022_comparison"),
            },
        },
        "gate2": {
            "passed": _audit_open_positions().get("passed") is True,
            "open_positions": _audit_open_positions(),
            "required_ohlcv_fields": ["Date", "Open", "High", "Low", "Close", "Volume"],
            "required_market_confirmation_fields": ["SPY", "QQQ"],
            "source_trade_fields": [
                "ticker",
                "signal_date",
                "entry_date",
                "entry_price",
                "close",
                "breakout_above_prior_20d_high_pct",
                "pnl",
                "pnl_pct_net",
                "vcp_candidate_rank_on_signal_date",
            ],
            "field_completeness": {
                "source_trade_count": source_trade_count,
                "enriched_trade_count": enriched_trade_count,
                "unavailable_context_count": by_status[STATUS_UNAVAILABLE]["trade_count"],
            },
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_changed": False,
            "note": (
                "This is post-entry attribution on already selected exp037 paper "
                "trades. It cannot reduce core survival or source candidate survival."
            ),
        },
        "gate4": {
            "passed": False,
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": (
                "Observed-only post-entry field. A later experiment must test an "
                "actionable PIT-safe exit/risk rule before any strategy change."
            ),
            "decision_evidence": decision_evidence,
        },
        "source_trade_count": source_trade_count,
        "enriched_trade_count": enriched_trade_count,
        "status_counts": status_counts,
        "by_status": by_status,
        "by_window_status": by_window_status,
        "by_rank_status": by_rank_status,
        "target_trades_by_window": rows_by_window,
        "non_tradable_counterfactual_without_failed_bucket": (
            _counterfactual_without_failed_bucket(top2, rows_by_window)
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "orders_changed": False,
            "live_capital_changed": False,
            "trade_enabled": False,
            "default_off_paper_only": True,
            "metadata_surface_changed": False,
            "read_only_attribution": True,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
        },
        "repro_command": (
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260526_008_vcp_top2_followthrough_failure_attribution.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
        },
        "related_files": [
            _repo_rel(SOURCE_EXP037_JSON),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }
    return payload


def _status_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| status | trades | total pnl | avg pnl | win rate | avg net pct |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for status, summary in payload["by_status"].items():
        lines.append(
            "| {status} | {trades} | {pnl} | {avg} | {win} | {pct} |".format(
                status=status,
                trades=summary["trade_count"],
                pnl=summary["total_pnl"],
                avg=summary["avg_pnl"],
                win=summary["win_rate"],
                pct=summary["avg_pnl_pct_net"],
            )
        )
    return lines


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | status | trades | total pnl | avg pnl | win rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for label, row in payload["by_window_status"].items():
        for status, summary in row["by_status"].items():
            if summary["trade_count"] == 0:
                continue
            lines.append(
                "| {label} | {status} | {trades} | {pnl} | {avg} | {win} |".format(
                    label=label,
                    status=status,
                    trades=summary["trade_count"],
                    pnl=summary["total_pnl"],
                    avg=summary["avg_pnl"],
                    win=summary["win_rate"],
                )
            )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    failed = payload["by_status"][STATUS_FAILED]
    counterfactual = payload["non_tradable_counterfactual_without_failed_bucket"]
    lines = [
        f"# {EXPERIMENT_ID} Kova VCP Top-2 Follow-Through Failure Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Source",
        "",
        "- Source population: `exp-20260525-037` top2_equal_notional selected paper trades.",
        "- Core, entry, ranking, sizing, exits, LLM/news, universe, and live/default orders unchanged.",
        "- Tested field is post-entry attribution only: `post_entry_follow_through_status_3d`.",
        "",
        "## Aggregate Buckets",
        "",
        *_status_table(payload),
        "",
        "## Window Buckets",
        "",
        *_window_table(payload),
        "",
        "## Failed Bucket Readout",
        "",
        f"- Failed bucket trades: `{failed['trade_count']}`.",
        f"- Failed bucket total PnL: `{failed['total_pnl']}`.",
        f"- Failed bucket average PnL: `{failed['avg_pnl']}`.",
        f"- Non-tradable PnL if failed bucket were removed after the fact: "
        f"`{counterfactual['remaining_pnl_after_removing_failed_bucket']}`.",
        "",
        "This counterfactual is not a trading rule. The failed bucket is known only after entry.",
        "",
        "## Gate 4",
        "",
        "No promotion was possible in this experiment because no actionable PIT-safe rule was tested.",
        "",
        "```json",
        json.dumps(payload["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Repro",
        "",
        "```powershell",
        payload["repro_command"],
        "```",
        "",
    ]
    return "\n".join(lines)


def _update_registry(payload: dict[str, Any]) -> None:
    if not EXPERIMENT_REGISTRY.exists():
        return
    registry = _load_json(EXPERIMENT_REGISTRY)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    updated = False
    for row in experiments:
        if not isinstance(row, dict):
            continue
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "lane": row.get("lane") or payload["registry_lane"],
                "owner": row.get("owner") or "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
        updated = True
        break
    if not updated:
        experiments.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "lane": payload["registry_lane"],
                "owner": "codex-kova",
                "hypothesis": payload["alpha_hypothesis"],
                "ticket_file": _repo_rel(TICKET_JSON),
                "updated_at": payload["created_at"],
                "result": {
                    "decision": payload["decision"],
                    "artifact": _repo_rel(ARTIFACT_MD),
                    "json": _repo_rel(OUT_JSON),
                    "summary": payload["summary"],
                },
            }
        )
    registry["updated_at"] = payload["created_at"]
    _write_json(EXPERIMENT_REGISTRY, registry)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": payload["experiment_id"],
            "status": payload["status"],
            "decision": payload["decision"],
            "lane": payload["lane"],
            "changed_variable": payload["changed_variable"],
            "summary": payload["summary"],
            "artifacts": payload["artifacts"],
            "repro_command": payload["repro_command"],
        },
    )
    _write_text(ARTIFACT_MD, _build_report(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_registry(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "status_counts": payload["status_counts"],
                "failed_bucket_pnl": payload["by_status"][STATUS_FAILED]["total_pnl"],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
