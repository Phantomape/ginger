"""exp-20260526-022: VCP base geometry / higher-low attribution.

This Kova-inspired attribution reads the accepted default-off VCP top-2 paper
sleeve after exp-20260526-007 rank-notional sizing and asks whether the
pre-signal base contains a clean rising risk level. The single observed field is
``pre_signal_base_geometry_bucket_v1``.

No entry, ranking, sizing, exit, universe, LLM/news, or live-order behavior is
changed. This is a PIT-safe metadata and attribution experiment only.
"""

from __future__ import annotations

import json
import math
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260526-022"
STEM = "vcp_base_geometry_higher_low_attribution"
TRIAL_FAMILY = "vcp_base_geometry_higher_low_attribution"
CHANGED_VARIABLE = "pre_signal_base_geometry_bucket_v1"
RULE_VERSION = "vcp_base_geometry_higher_low_attribution_v1"

SOURCE_EXP007_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260526-007"
    / "vcp_rank_notional_profile.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOCS_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
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

SOURCE_VARIANT = "rank2_125"
LOOKBACK_TRADING_DAYS = 30

BUCKET_CONSTRUCTIVE = "constructive_higher_low_base"
BUCKET_NONCONSTRUCTIVE = "nonconstructive_or_lower_low_base"
BUCKET_INSUFFICIENT = "insufficient_swing_low_structure"
BUCKET_UNAVAILABLE = "unavailable"
BUCKET_ORDER = [
    BUCKET_CONSTRUCTIVE,
    BUCKET_NONCONSTRUCTIVE,
    BUCKET_INSUFFICIENT,
    BUCKET_UNAVAILABLE,
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


def _base_context_shell(
    *,
    trade: dict[str, Any],
    bucket: str,
    available: bool,
    reason: str | None,
    pivot_level: float | None,
    pivot_source: str | None,
    prior_rows: list[dict[str, Any]] | None = None,
    swing_lows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = prior_rows or []
    lows = swing_lows or []
    latest = lows[-1] if lows else None
    prior = lows[-2] if len(lows) >= 2 else None
    latest_low = _num(latest.get("low")) if latest else None
    prior_low = _num(prior.get("low")) if prior else None
    higher_low_pairs = 0
    for left, right in zip(lows[-3:], lows[-2:]):
        left_low = _num(left.get("low"))
        right_low = _num(right.get("low"))
        if left_low is not None and right_low is not None and right_low > left_low:
            higher_low_pairs += 1
    return {
        "pre_signal_base_geometry_rule_version": RULE_VERSION,
        "pre_signal_base_geometry_bucket_v1": bucket,
        "pre_signal_base_geometry_available": available,
        "pre_signal_base_geometry_unavailable_reason": reason,
        "pre_signal_base_geometry_known_at": (
            "after_signal_date_close_before_next_open_paper_entry; "
            "base geometry uses only ticker OHLCV rows with Date < signal_date"
        ),
        "pre_signal_base_geometry_alters_orders": False,
        "pre_signal_base_geometry_trade_enabled": False,
        "pre_signal_base_geometry_lookback_trading_days": LOOKBACK_TRADING_DAYS,
        "breakout_pivot_level": _round(pivot_level, 4),
        "breakout_pivot_source": pivot_source,
        "signal_close": _round(
            _num(trade.get("close") if "close" in trade else trade.get("Close")),
            4,
        ),
        "signal_date": _date10(trade.get("signal_date") or trade.get("date")),
        "pre_signal_observed_start_date": _row_date(rows[0]) if rows else None,
        "pre_signal_observed_end_date": _row_date(rows[-1]) if rows else None,
        "pre_signal_observed_row_count": len(rows),
        "pre_signal_swing_low_count": len(lows),
        "pre_signal_swing_lows_last3": [
            {"date": row.get("date"), "low": _round(row.get("low"), 4)}
            for row in lows[-3:]
        ],
        "latest_pre_signal_swing_low_date": latest.get("date") if latest else None,
        "latest_pre_signal_swing_low": _round(latest_low, 4),
        "prior_pre_signal_swing_low_date": prior.get("date") if prior else None,
        "prior_pre_signal_swing_low": _round(prior_low, 4),
        "latest_swing_low_vs_prior_pct": _round(
            latest_low / prior_low - 1.0,
            6,
        )
        if latest_low is not None and prior_low and prior_low > 0
        else None,
        "latest_swing_low_vs_pivot_pct": _round(
            latest_low / pivot_level - 1.0,
            6,
        )
        if latest_low is not None and pivot_level and pivot_level > 0
        else None,
        "risk_to_pivot_pct": _round(
            (pivot_level - latest_low) / pivot_level,
            6,
        )
        if latest_low is not None and pivot_level and pivot_level > 0
        else None,
        "higher_low_pair_count_last3": higher_low_pairs,
    }


def _find_swing_lows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    swing_lows: list[dict[str, Any]] = []
    lows = [_row_value(row, "Low") for row in rows]
    dates = [_row_date(row) for row in rows]
    for idx in range(1, len(rows) - 1):
        low = lows[idx]
        left = lows[idx - 1]
        right = lows[idx + 1]
        if low is None or left is None or right is None:
            continue
        if (low < left and low <= right) or (low <= left and low < right):
            swing_lows.append({"date": dates[idx], "low": low, "position": idx})
    return swing_lows


def compute_pre_signal_base_geometry_context(
    rows: list[dict[str, Any]],
    trade: dict[str, Any],
    *,
    lookback_trading_days: int = LOOKBACK_TRADING_DAYS,
) -> dict[str, Any]:
    """Classify prior base geometry using only rows before the signal date.

    The constructive bucket requires the latest identified pre-signal swing low
    to be strictly above the prior swing low and below the inferred breakout
    pivot. Equal lows do not pass.
    """

    signal_date = _date10(trade.get("signal_date") or trade.get("date"))
    pivot_level, pivot_source = infer_breakout_pivot_level(trade)
    if not signal_date:
        return _base_context_shell(
            trade=trade,
            bucket=BUCKET_UNAVAILABLE,
            available=False,
            reason="missing_signal_date",
            pivot_level=pivot_level,
            pivot_source=pivot_source,
        )
    if pivot_level is None or pivot_level <= 0:
        return _base_context_shell(
            trade=trade,
            bucket=BUCKET_UNAVAILABLE,
            available=False,
            reason="missing_breakout_pivot",
            pivot_level=pivot_level,
            pivot_source=pivot_source,
        )
    if not rows:
        return _base_context_shell(
            trade=trade,
            bucket=BUCKET_UNAVAILABLE,
            available=False,
            reason="missing_ticker_ohlcv_rows",
            pivot_level=pivot_level,
            pivot_source=pivot_source,
        )

    sorted_rows = sorted(rows, key=_row_date)
    prior_rows = [row for row in sorted_rows if _row_date(row) < signal_date]
    lookback_rows = prior_rows[-lookback_trading_days:]
    if len(lookback_rows) < 5:
        return _base_context_shell(
            trade=trade,
            bucket=BUCKET_UNAVAILABLE,
            available=False,
            reason="fewer_than_5_prior_rows",
            pivot_level=pivot_level,
            pivot_source=pivot_source,
            prior_rows=lookback_rows,
        )
    missing_low_dates = [_row_date(row) for row in lookback_rows if _row_value(row, "Low") is None]
    if missing_low_dates:
        context = _base_context_shell(
            trade=trade,
            bucket=BUCKET_UNAVAILABLE,
            available=False,
            reason="missing_low_in_prior_window",
            pivot_level=pivot_level,
            pivot_source=pivot_source,
            prior_rows=lookback_rows,
        )
        context["missing_low_dates"] = missing_low_dates[:10]
        return context

    swing_lows = _find_swing_lows(lookback_rows)
    if len(swing_lows) < 2:
        return _base_context_shell(
            trade=trade,
            bucket=BUCKET_INSUFFICIENT,
            available=True,
            reason=None,
            pivot_level=pivot_level,
            pivot_source=pivot_source,
            prior_rows=lookback_rows,
            swing_lows=swing_lows,
        )

    prior_low = _num(swing_lows[-2].get("low"))
    latest_low = _num(swing_lows[-1].get("low"))
    constructive = (
        latest_low is not None
        and prior_low is not None
        and latest_low > prior_low
        and latest_low < pivot_level
    )
    return _base_context_shell(
        trade=trade,
        bucket=BUCKET_CONSTRUCTIVE if constructive else BUCKET_NONCONSTRUCTIVE,
        available=True,
        reason=None,
        pivot_level=pivot_level,
        pivot_source=pivot_source,
        prior_rows=lookback_rows,
        swing_lows=swing_lows,
    )


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
                "bucket": row.get("pre_signal_base_geometry_bucket_v1"),
                "pnl": _round(row.get("pnl"), 2),
                "pnl_pct_net": _round(row.get("pnl_pct_net"), 6),
                "latest_swing_low_vs_prior_pct": row.get("latest_swing_low_vs_prior_pct"),
                "risk_to_pivot_pct": row.get("risk_to_pivot_pct"),
                "pre_signal_swing_lows_last3": row.get("pre_signal_swing_lows_last3"),
            }
        )
    return out


def _trade_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl_values = [float(row.get("pnl") or 0.0) for row in rows]
    pnl_pct_values = _pct_sample(rows, "pnl_pct_net")
    risk_values = _pct_sample(rows, "risk_to_pivot_pct")
    higher_low_values = _pct_sample(rows, "latest_swing_low_vs_prior_pct")
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
        "avg_risk_to_pivot_pct": _round(sum(risk_values) / len(risk_values), 6)
        if risk_values
        else None,
        "avg_latest_swing_low_vs_prior_pct": _round(
            sum(higher_low_values) / len(higher_low_values),
            6,
        )
        if higher_low_values
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


def _group_by_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("pre_signal_base_geometry_bucket_v1") or BUCKET_UNAVAILABLE)].append(
            row
        )
    return OrderedDict((bucket, _trade_summary(grouped.get(bucket, []))) for bucket in BUCKET_ORDER)


def _group_by_window_bucket(
    rows_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    out: "OrderedDict[str, Any]" = OrderedDict()
    for label in WINDOWS:
        rows = rows_by_window.get(label, [])
        out[label] = {
            "all_top2_rank_profile_trades": _trade_summary(rows),
            "by_bucket": _group_by_bucket(rows),
        }
    return out


def _group_by_rank_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
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
            _group_by_bucket(
                [row for row in rows if str(row.get("vcp_candidate_rank_on_signal_date")) == rank]
            ),
        )
        for rank in ranks
    )


def _load_source_rank_profile() -> dict[str, Any]:
    source = _load_json(SOURCE_EXP007_JSON)
    variant = source.get("profile_results", {}).get(SOURCE_VARIANT)
    if not isinstance(variant, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} profile result")
    trades_by_window = variant.get("target_trades_by_window")
    if not isinstance(trades_by_window, dict):
        raise ValueError(f"Missing exp007 {SOURCE_VARIANT} target_trades_by_window")
    return {"source": source, "variant": variant, "target_trades_by_window": trades_by_window}


def _enrich_trades(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for label, cfg in WINDOWS.items():
        snapshot = _load_snapshot(cfg["snapshot"])
        source_rows = source["target_trades_by_window"].get(label, [])
        enriched: list[dict[str, Any]] = []
        for trade in source_rows:
            ticker = str(trade.get("ticker") or "").upper()
            context = compute_pre_signal_base_geometry_context(
                snapshot.get(ticker, []),
                trade,
            )
            enriched.append({**trade, "window": label, **context})
        out[label] = enriched
    return out


def _flatten(rows_by_window: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [row for rows in rows_by_window.values() for row in rows]


def _combined_nonconstructive_summary(by_bucket: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for bucket in (BUCKET_NONCONSTRUCTIVE, BUCKET_INSUFFICIENT, BUCKET_UNAVAILABLE):
        rows.extend(by_bucket[bucket].get("worst_trades_source_rows", []))
    return _trade_summary(rows)


def _decision(
    *,
    all_rows: list[dict[str, Any]],
    by_bucket: dict[str, Any],
    by_window_bucket: dict[str, Any],
) -> tuple[str, str, dict[str, Any]]:
    constructive = by_bucket[BUCKET_CONSTRUCTIVE]
    nonconstructive_rows = [
        row
        for row in all_rows
        if row.get("pre_signal_base_geometry_bucket_v1") != BUCKET_CONSTRUCTIVE
    ]
    nonconstructive = _trade_summary(nonconstructive_rows)
    constructive_avg = constructive["avg_pnl"]
    nonconstructive_avg = nonconstructive["avg_pnl"]
    constructive_pnls_by_window = {
        label: by_window_bucket[label]["by_bucket"][BUCKET_CONSTRUCTIVE]["total_pnl"]
        for label in WINDOWS
    }
    constructive_trade_counts_by_window = {
        label: by_window_bucket[label]["by_bucket"][BUCKET_CONSTRUCTIVE]["trade_count"]
        for label in WINDOWS
    }
    positive_constructive_windows = [
        label for label, pnl in constructive_pnls_by_window.items() if pnl is not None and pnl > 0
    ]
    concentration_passed = (
        constructive["max_single_positive_pnl_share"] is not None
        and constructive["positive_pnl_hhi"] is not None
        and constructive["max_single_positive_pnl_share"] < 0.40
        and constructive["positive_pnl_hhi"] < 0.30
    )
    promising = (
        constructive["trade_count"] >= 20
        and constructive["total_pnl"] is not None
        and constructive["total_pnl"] > 0
        and constructive_avg is not None
        and nonconstructive_avg is not None
        and constructive_avg > nonconstructive_avg
        and len(positive_constructive_windows) >= 2
        and concentration_passed
    )
    evidence = {
        "constructive_trade_count_min_20": constructive["trade_count"] >= 20,
        "constructive_positive_aggregate": constructive["total_pnl"] is not None
        and constructive["total_pnl"] > 0,
        "constructive_positive_windows": positive_constructive_windows,
        "constructive_trade_counts_by_window": constructive_trade_counts_by_window,
        "constructive_avg_pnl": _round(constructive_avg, 2),
        "nonconstructive_or_unavailable_avg_pnl": _round(nonconstructive_avg, 2),
        "constructive_beats_nonconstructive_avg_pnl": (
            constructive_avg is not None
            and nonconstructive_avg is not None
            and constructive_avg > nonconstructive_avg
        ),
        "constructive_concentration_passed": concentration_passed,
        "constructive_max_single_positive_pnl_share": constructive[
            "max_single_positive_pnl_share"
        ],
        "constructive_positive_pnl_hhi": constructive["positive_pnl_hhi"],
    }
    if promising:
        return (
            "observed_only_promising_base_geometry_attribution",
            (
                "The pre-signal constructive higher-low base bucket is large enough, "
                "profitable, better on average than the rest of the sleeve, and not "
                "overly concentrated. It can justify a later closed forward "
                "replacement-value test, but no allocation change is made here."
            ),
            evidence,
        )
    return (
        "observed_only_no_actionable_base_geometry_split",
        (
            "The pre-signal higher-low base geometry bucket did not clear the "
            "observed-only attribution bar. Keep the VCP top-2 rank-notional sleeve "
            "unchanged and avoid turning this frozen-sample split into a gate."
        ),
        evidence,
    )


def _build_payload() -> dict[str, Any]:
    source = _load_source_rank_profile()
    rows_by_window = _enrich_trades(source)
    all_rows = _flatten(rows_by_window)
    by_bucket = _group_by_bucket(all_rows)
    by_window_bucket = _group_by_window_bucket(rows_by_window)
    by_rank_bucket = _group_by_rank_bucket(all_rows)
    decision, interpretation, decision_evidence = _decision(
        all_rows=all_rows,
        by_bucket=by_bucket,
        by_window_bucket=by_window_bucket,
    )

    source_variant = source["variant"]
    source_trade_count = sum(len(rows) for rows in source["target_trades_by_window"].values())
    bucket_counts = {
        bucket: by_bucket[bucket]["trade_count"]
        for bucket in BUCKET_ORDER
        if by_bucket[bucket]["trade_count"]
    }
    open_positions_audit = _audit_open_positions()

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
            "Kova-style higher-low base geometry before an accepted VCP breakout may "
            "identify candidates with cleaner risk levels and better replacement "
            "value inside the default-off VCP top-2 rank-notional paper sleeve."
        ),
        "history_check": {
            "exp-20260525-022": "Accepted QQQ-confirmed VCP top-1 paper sleeve.",
            "exp-20260525-027": "Kova pocket-pivot support gate rejected versus exp022.",
            "exp-20260525-030": "Event context useful versus core but weaker than exp022.",
            "exp-20260525-032": "Volume dry-up gate did not become a replacement rule.",
            "exp-20260525-033": "Dossier/catalyst support separated outcomes but did not favor support buckets.",
            "exp-20260525-036": "Late_strong VCP weakness was underparticipation/rank-depth scarcity.",
            "exp-20260525-037": "Accepted default-off top-2 VCP paper expansion.",
            "exp-20260526-007": "Accepted top-2 rank-notional profile [1.0, 1.25].",
            "exp-20260526-008": "Post-entry pivot failure was useful attribution only and not actionable.",
        },
        "single_causal_variable": {
            "name": CHANGED_VARIABLE,
            "buckets": BUCKET_ORDER,
            "lookback_trading_days": LOOKBACK_TRADING_DAYS,
            "swing_low_definition": (
                "A pre-signal row whose Low is strictly lower than one neighbor and "
                "not higher than the other neighbor inside the prior lookback window."
            ),
            "constructive_definition": (
                "Latest pre-signal swing low is strictly above the prior swing low "
                "and below the inferred breakout pivot."
            ),
            "equal_low_handling": "Equal latest/prior swing lows do not pass.",
            "date_boundary": "Only rows with Date < signal_date are inspected.",
            "known_at": "after_signal_date_close_before_next_open_paper_entry",
        },
        "acceptance_standard": {
            "promotion_allowed_in_this_experiment": False,
            "reason": (
                "This run tests a metadata attribution field only; no replacement "
                "or allocation rule is promoted from this frozen sample."
            ),
            "promising_attribution_gate": (
                "constructive bucket has >=20 trades, positive aggregate PnL, "
                "positive PnL in at least two windows, better average PnL than the "
                "rest of the sleeve, max single positive contribution <40%, and "
                "positive PnL HHI <0.30"
            ),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": WINDOWS,
            "source_population": _repo_rel(SOURCE_EXP007_JSON),
            "source_variant": SOURCE_VARIANT,
            "paper_entry": "next available open from exp007 source sleeve",
            "paper_exit": "10 trading days after signal from exp007 source sleeve",
            "rank_notional_profile": [1.0, 1.25],
            "changed_core_logic": False,
        },
        "gate1": {
            "passed": True,
            "baseline_core_stack": "exp-20260517-009 accepted core stack",
            "source_paper_baseline": "exp-20260526-007 rank2_125 VCP top-2 paper sleeve",
            "source_exp007_summary": {
                "expected_value_score_delta_vs_core": source_variant.get(
                    "expected_value_score_delta"
                ),
                "total_pnl_delta_vs_core": source_variant.get("total_pnl_delta"),
                "target_trade_count": source_trade_count,
                "target_trade_summary": source_variant.get("target_trade_summary"),
                "source_exp037_comparison": source_variant.get("source_exp037_comparison"),
            },
        },
        "gate2": {
            "passed": open_positions_audit.get("passed") is True,
            "open_positions": open_positions_audit,
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
                "rank_notional_scalar",
            ],
            "field_completeness": {
                "source_trade_count": source_trade_count,
                "enriched_trade_count": len(all_rows),
                "unavailable_context_count": by_bucket[BUCKET_UNAVAILABLE]["trade_count"],
            },
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "core_survival_changed": False,
            "source_paper_survival_changed": False,
            "note": (
                "This is pre-signal attribution on already selected exp007 paper "
                "trades. It cannot reduce core survival or source candidate survival."
            ),
        },
        "gate4": {
            "passed": False,
            "strategy_replacement_tested": False,
            "promotion_grade": False,
            "reason": (
                "Observed-only metadata attribution. A later closed forward or "
                "Gate 1-4 replacement test is required before any strategy change."
            ),
            "decision_evidence": decision_evidence,
        },
        "source_trade_count": source_trade_count,
        "enriched_trade_count": len(all_rows),
        "bucket_counts": bucket_counts,
        "by_bucket": by_bucket,
        "by_window_bucket": by_window_bucket,
        "by_rank_bucket": by_rank_bucket,
        "target_trades_by_window": rows_by_window,
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
            "exp_20260526_022_vcp_base_geometry_higher_low_attribution.py"
        ),
        "artifacts": {
            "json": _repo_rel(OUT_JSON),
            "markdown": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "ticket": _repo_rel(TICKET_JSON),
            "docs_ticket": _repo_rel(DOCS_TICKET_JSON),
        },
        "related_files": [
            _repo_rel(SOURCE_EXP007_JSON),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "why_not_other_changes": (
            "Did not retune VCP compression/breakout, QQQ/SPY, top-N, rank-notional "
            "profile, sizing, exits, universe, LLM/news, live/default orders, pocket "
            "pivot, catalyst, volume dry-up, or post-entry follow-through thresholds."
        ),
    }
    return payload


def _bucket_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| bucket | trades | total pnl | avg pnl | win rate | avg risk-to-pivot |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for bucket, summary in payload["by_bucket"].items():
        lines.append(
            "| {bucket} | {trades} | {pnl} | {avg} | {win} | {risk} |".format(
                bucket=bucket,
                trades=summary["trade_count"],
                pnl=summary["total_pnl"],
                avg=summary["avg_pnl"],
                win=summary["win_rate"],
                risk=summary["avg_risk_to_pivot_pct"],
            )
        )
    return lines


def _window_table(payload: dict[str, Any]) -> list[str]:
    lines = [
        "| window | bucket | trades | total pnl | avg pnl | win rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for label, row in payload["by_window_bucket"].items():
        for bucket, summary in row["by_bucket"].items():
            if summary["trade_count"] == 0:
                continue
            lines.append(
                "| {label} | {bucket} | {trades} | {pnl} | {avg} | {win} |".format(
                    label=label,
                    bucket=bucket,
                    trades=summary["trade_count"],
                    pnl=summary["total_pnl"],
                    avg=summary["avg_pnl"],
                    win=summary["win_rate"],
                )
            )
    return lines


def _build_report(payload: dict[str, Any]) -> str:
    constructive = payload["by_bucket"][BUCKET_CONSTRUCTIVE]
    lines = [
        f"# {EXPERIMENT_ID} VCP Base Geometry / Higher-Low Attribution",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        payload["summary"],
        "",
        "## Source",
        "",
        "- Source population: `exp-20260526-007` `rank2_125` selected paper trades.",
        "- Core, VCP definition, QQQ/SPY gate, top-2 selection, rank-notional profile, exits, LLM/news, universe, and live/default orders unchanged.",
        "- Tested field: `pre_signal_base_geometry_bucket_v1`.",
        "",
        "## Aggregate Buckets",
        "",
        *_bucket_table(payload),
        "",
        "## Window Buckets",
        "",
        *_window_table(payload),
        "",
        "## Constructive Bucket Readout",
        "",
        f"- Constructive bucket trades: `{constructive['trade_count']}`.",
        f"- Constructive bucket total PnL: `{constructive['total_pnl']}`.",
        f"- Constructive bucket average PnL: `{constructive['avg_pnl']}`.",
        f"- Max single positive PnL share: `{constructive['max_single_positive_pnl_share']}`.",
        f"- Positive PnL HHI: `{constructive['positive_pnl_hhi']}`.",
        "",
        "## Gate 4",
        "",
        "No strategy promotion was possible in this experiment because this is read-only attribution.",
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
    ticket_payload = {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "registry_lane": payload["registry_lane"],
        "owner": "codex-kova",
        "hypothesis": payload["alpha_hypothesis"],
        "change_type": "vcp_base_geometry_higher_low_attribution",
        "mechanism_family": "volatility_contraction_breakout",
        "trial_family": payload["trial_family"],
        "trial_variant_id": "vcp_base_geometry_higher_low_risk_level",
        "single_causal_variable": payload["changed_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": 8,
        "nearby_prior_experiments": list(payload["history_check"].keys()),
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_daily_ohlcv_base_geometry_field",
        "baseline_result_file": _repo_rel(SOURCE_EXP007_JSON),
        "allowed_write_scope": [
            _repo_rel(Path("quant/experiments/exp_20260526_022_vcp_base_geometry_higher_low_attribution.py")),
            _repo_rel(Path("quant/test_vcp_base_geometry_higher_low_attribution.py")),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOCS_TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(EXPERIMENT_REGISTRY),
            _repo_rel(Path("docs/current_state.md")),
            _repo_rel(Path("docs/alpha-optimization-playbook.md")),
        ],
        "must_not_touch": [
            "quant/volatility_contraction_paper_sleeve.py",
            "quant/run.py",
            "quant/backtester.py",
        ],
        "locked_variables": [
            "core entries",
            "VCP compression and breakout",
            "QQQ/SPY gate",
            "top2 selection",
            "rank-notional profile",
            "sizing",
            "exits",
            "LLM/news",
            "universe",
            "live/default orders",
        ],
        "evaluation_windows": [
            {"start": cfg["start"], "end": cfg["end"]} for cfg in WINDOWS.values()
        ],
        "acceptance_rule": payload["acceptance_standard"],
        "created_at": payload["created_at"],
        "completed_at": payload["created_at"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["summary"],
            "artifact": payload["artifacts"]["markdown"],
            "json": payload["artifacts"]["json"],
        },
        "summary": payload["summary"],
        "artifacts": payload["artifacts"],
        "repro_command": payload["repro_command"],
    }
    _write_json(TICKET_JSON, ticket_payload)
    _write_json(DOCS_TICKET_JSON, ticket_payload)
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
                "bucket_counts": payload["bucket_counts"],
                "constructive_bucket_pnl": payload["by_bucket"][BUCKET_CONSTRUCTIVE][
                    "total_pnl"
                ],
                "artifact": payload["artifacts"]["markdown"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
