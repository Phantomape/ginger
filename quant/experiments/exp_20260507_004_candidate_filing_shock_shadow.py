"""exp-20260507-004 candidate-level SEC/earnings filing-shock shadow tags.

This is a shadow-only audit. It captures the existing post-filter/post-sizing
candidate rows during canonical backtests, tags each row with the latest
PIT-safe SEC filing-shock context, and measures forward returns by tag. It does
not change signal generation, filters, ranking, sizing, exits, orders, or
production adapters.
"""

from __future__ import annotations

import inspect
import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-004"
STEM = "exp_20260507_004_candidate_filing_shock_shadow"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_candidate_filing_shock_shadow.md"
)
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_earnings_filing_shock_candidate_tags_exp-20260507-004_20260507.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

RECENT_FILING_LOOKBACK_TRADING_DAYS = 20
ROUND_TRIP_COST = 0.0035
HORIZONS = (5, 10, 20, 60)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "coverage_report": "data/non_ohlcv/backtest_coverage_20251023_20260421.json",
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "coverage_report": "data/non_ohlcv/backtest_coverage_20250423_20251022.json",
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "coverage_report": "data/non_ohlcv/backtest_coverage_20241002_20250422.json",
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    if isinstance(value, str) and value.strip():
        try:
            out = float(value)
        except ValueError:
            return None
        return out if math.isfinite(out) else None
    return None


def _round(value: Any, digits: int = 4) -> Any:
    numeric = _as_float(value)
    if numeric is None:
        return None
    return round(numeric, digits)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    raw = payload.get("ohlcv") or payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in raw.items():
        converted = []
        for row in rows or []:
            date = str(row.get("Date") or row.get("date") or "")[:10]
            close = _as_float(row.get("Close") if "Close" in row else row.get("close"))
            open_price = _as_float(row.get("Open") if "Open" in row else row.get("open"))
            if not date or close is None:
                continue
            converted.append(
                {
                    "date": date,
                    "close": close,
                    "open": open_price if open_price is not None else close,
                }
            )
        if converted:
            out[str(ticker).upper()] = sorted(converted, key=lambda item: item["date"])
    return out


def _idx_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _forward_returns(
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> dict[str, Any]:
    rows = snapshot.get(ticker.upper()) or []
    start_idx = _idx_on_or_after(rows, date_value)
    if start_idx is None:
        return {f"ret_{horizon}d": None for horizon in HORIZONS} | {
            "base_date": None,
            "base_close": None,
        }
    base = _as_float(rows[start_idx].get("close"))
    out: dict[str, Any] = {
        "base_date": rows[start_idx]["date"],
        "base_close": base,
    }
    for horizon in HORIZONS:
        horizon_idx = start_idx + horizon
        if base is None or base <= 0 or horizon_idx >= len(rows):
            out[f"ret_{horizon}d"] = None
            out[f"end_date_{horizon}d"] = None
            continue
        end_close = _as_float(rows[horizon_idx].get("close"))
        out[f"ret_{horizon}d"] = (
            (end_close / base) - 1.0 - ROUND_TRIP_COST
            if end_close is not None
            else None
        )
        out[f"end_date_{horizon}d"] = rows[horizon_idx]["date"]
    return out


def _market_trading_day_distance(
    snapshot: dict[str, list[dict[str, Any]]],
    earlier: str,
    later: str,
) -> int | None:
    rows = snapshot.get("SPY") or next(iter(snapshot.values()), [])
    left = _idx_on_or_after(rows, earlier)
    right = _idx_on_or_after(rows, later)
    if left is None or right is None:
        return None
    return right - left


def _date_from_feature_file(path: Path) -> str | None:
    suffix = path.stem.rsplit("_", 1)[-1]
    if len(suffix) != 8 or not suffix.isdigit():
        return None
    return f"{suffix[:4]}-{suffix[4:6]}-{suffix[6:]}"


def _load_sec_features(start: str, end: str, lookback_calendar_days: int = 45) -> list[dict[str, Any]]:
    min_date = (datetime.fromisoformat(start) - timedelta(days=lookback_calendar_days)).date().isoformat()
    rows: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_features_*.jsonl")):
        file_date = _date_from_feature_file(path)
        if not file_date or file_date < min_date or file_date > end:
            continue
        for row in _load_jsonl(path):
            accepted = row.get("accepted_datetime") or row.get("accepted_at")
            usable = row.get("usable_trade_date")
            ticker = str(row.get("ticker") or "").upper()
            row["ticker"] = ticker
            row["pit_safe"] = bool(accepted and usable and ticker)
            if ticker:
                rows.append(row)
    return rows


def _build_events_by_ticker(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    events_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        usable = str(row.get("usable_trade_date") or "")[:10]
        if ticker and usable and row.get("pit_safe"):
            events_by_ticker[ticker].append(row)
    for ticker in events_by_ticker:
        events_by_ticker[ticker].sort(
            key=lambda item: (
                str(item.get("usable_trade_date") or ""),
                str(item.get("accepted_datetime") or item.get("accepted_at") or ""),
            ),
            reverse=True,
        )
    return events_by_ticker


def _latest_recent_event(
    events_by_ticker: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> tuple[dict[str, Any] | None, int | None]:
    best: dict[str, Any] | None = None
    best_distance: int | None = None
    for row in events_by_ticker.get(ticker.upper(), []):
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable or usable > date_value:
            continue
        distance = _market_trading_day_distance(snapshot, usable, date_value)
        if distance is None or distance < 0 or distance > RECENT_FILING_LOOKBACK_TRADING_DAYS:
            continue
        if best is None or distance < (best_distance or 10**9):
            best = row
            best_distance = distance
    return best, best_distance


def _directional_field_counts(row: dict[str, Any]) -> tuple[int, int, list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    for field in (
        "eps_surprise",
        "revenue_surprise",
        "gross_margin_delta",
        "fcf_to_net_income_gap",
    ):
        value = _as_float(row.get(field))
        if value is None:
            continue
        if value > 0:
            positive.append(field)
        elif value < 0:
            negative.append(field)

    guidance = str(row.get("guidance_raise_cut") or "").strip().lower()
    if guidance in {"raise", "raised", "guidance_raise"}:
        positive.append("guidance_raise_cut")
    elif guidance in {"cut", "lowered", "guidance_cut"}:
        negative.append("guidance_raise_cut")
    return len(positive), len(negative), positive, negative


def _classify_filing_shock(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {
            "filing_shock_tag": "A_no_recent_filing_event",
            "positive_evidence_fields": [],
            "negative_evidence_fields": [],
            "classification_reason": "no PIT-safe SEC filing within lookback",
        }
    positive_count, negative_count, positive_fields, negative_fields = _directional_field_counts(event)
    if positive_count > 0 and negative_count == 0:
        return {
            "filing_shock_tag": "B_positive_filing_shock",
            "positive_evidence_fields": positive_fields,
            "negative_evidence_fields": negative_fields,
            "classification_reason": "positive directional same-row financial evidence",
        }
    if negative_count > 0 and positive_count == 0:
        return {
            "filing_shock_tag": "C_negative_filing_shock",
            "positive_evidence_fields": positive_fields,
            "negative_evidence_fields": negative_fields,
            "classification_reason": "negative directional same-row financial evidence",
        }
    return {
        "filing_shock_tag": "D_unclear_or_missing_data",
        "positive_evidence_fields": positive_fields,
        "negative_evidence_fields": negative_fields,
        "classification_reason": "recent SEC event exists but directional financial shock fields are missing or mixed",
    }


def _event_reference(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    fields = (
        "ticker",
        "event_date",
        "usable_trade_date",
        "form_type",
        "accepted_datetime",
        "fiscal_period_end",
        "eps_surprise",
        "revenue_surprise",
        "gross_margin_delta",
        "fcf_to_net_income_gap",
        "inventory_growth",
        "receivables_growth",
        "guidance_raise_cut",
        "eight_k_item_type",
        "data_source",
        "pit_safe",
        "source_accession",
        "field_availability",
        "gap_reasons",
    )
    return {field: event.get(field) for field in fields}


def _signal_key(sig: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(sig.get("ticker") or "").upper(),
        str(sig.get("strategy") or ""),
        str(sig.get("entry_price") or ""),
        str(sig.get("stop_price") or ""),
    )


def _runtime_today() -> str | None:
    for frame_info in inspect.stack():
        today = frame_info.frame.f_locals.get("today")
        if today is not None and hasattr(today, "date"):
            return str(today.date())
    return None


def _sizing_multipliers(sig: dict[str, Any]) -> dict[str, Any]:
    sizing = sig.get("sizing") or {}
    return {
        key: value
        for key, value in sizing.items()
        if key.endswith("_applied") or "risk_multiplier" in key
    }


def _candidate_record(
    *,
    window_name: str,
    date_value: str,
    rank: int,
    sig: dict[str, Any],
    status: str,
    available_slots: Any,
    events_by_ticker: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    ticker = str(sig.get("ticker") or "").upper()
    event, distance = _latest_recent_event(events_by_ticker, snapshot, ticker, date_value)
    classification = _classify_filing_shock(event)
    sizing = sig.get("sizing") or {}
    return {
        "window": window_name,
        "candidate_date": date_value,
        "ticker": ticker,
        "strategy": sig.get("strategy"),
        "sector": sig.get("sector", "Unknown"),
        "candidate_rank": rank,
        "plan_status": status,
        "available_slots": available_slots,
        "confidence_score": sig.get("confidence_score"),
        "trade_quality_score": sig.get("trade_quality_score"),
        "entry_price": sig.get("entry_price"),
        "stop_price": sig.get("stop_price"),
        "target_price": sig.get("target_price"),
        "shares_to_buy": sizing.get("shares_to_buy"),
        "risk_pct": sizing.get("risk_pct"),
        "position_value_usd": sizing.get("position_value_usd"),
        "sizing_multipliers": _sizing_multipliers(sig),
        "recent_filing_lookback_trading_days": RECENT_FILING_LOOKBACK_TRADING_DAYS,
        "recent_filing_distance_trading_days": distance,
        "recent_filing": _event_reference(event),
        **classification,
        **_forward_returns(snapshot, ticker, date_value),
    }


def _capture_plan_candidates(
    *,
    window_name: str,
    events_by_ticker: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, list[dict[str, Any]]],
    captured: list[dict[str, Any]],
):
    original = bt.plan_entry_candidates

    def patched(signals, open_positions, **kwargs):
        input_signals = list(signals or [])
        planned, entry_plan = original(signals, open_positions, **kwargs)
        date_value = _runtime_today()
        if date_value is None:
            return planned, entry_plan

        selected_ids = {id(sig) for sig in planned}
        slot_sliced_ids = {id(sig) for sig in entry_plan.get("slot_sliced_signals") or []}
        deferred_keys = {
            _signal_key(sig)
            for sig in entry_plan.get("deferred_breakout_signals") or []
        }
        available_slots = entry_plan.get("available_slots")

        for rank, sig in enumerate(input_signals, start=1):
            key = _signal_key(sig)
            if key in deferred_keys:
                status = "scarce_slot_breakout_deferred"
            elif id(sig) in selected_ids:
                status = "selected_by_entry_plan"
            elif id(sig) in slot_sliced_ids:
                status = "slot_sliced"
            else:
                status = "not_selected_by_entry_plan"
            captured.append(
                _candidate_record(
                    window_name=window_name,
                    date_value=date_value,
                    rank=rank,
                    sig=sig,
                    status=status,
                    available_slots=available_slots,
                    events_by_ticker=events_by_ticker,
                    snapshot=snapshot,
                )
            )
        return planned, entry_plan

    bt.plan_entry_candidates = patched
    return original


def _summarize_values(values: list[Any]) -> dict[str, Any]:
    clean = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and math.isfinite(float(value))
    ]
    if not clean:
        return {
            "count": 0,
            "avg_pct": None,
            "median_pct": None,
            "win_rate": None,
            "best_pct": None,
            "worst_pct": None,
        }
    return {
        "count": len(clean),
        "avg_pct": round(mean(clean) * 100.0, 4),
        "median_pct": round(median(clean) * 100.0, 4),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "best_pct": round(max(clean) * 100.0, 4),
        "worst_pct": round(min(clean) * 100.0, 4),
    }


def _forward_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"{horizon}d": _summarize_values([row.get(f"ret_{horizon}d") for row in rows])
        for horizon in HORIZONS
    }


def _tag_strategy_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    tags = [
        "A_no_recent_filing_event",
        "B_positive_filing_shock",
        "C_negative_filing_shock",
        "D_unclear_or_missing_data",
    ]
    strategies = sorted({str(row.get("strategy") or "unknown") for row in rows})
    for tag in tags:
        tag_rows = [row for row in rows if row.get("filing_shock_tag") == tag]
        out[tag] = {
            "candidate_count": len(tag_rows),
            "forward_returns": _forward_summary(tag_rows),
            "by_strategy": {
                strategy: {
                    "candidate_count": len([
                        row for row in tag_rows
                        if str(row.get("strategy") or "unknown") == strategy
                    ]),
                    "forward_returns": _forward_summary([
                        row for row in tag_rows
                        if str(row.get("strategy") or "unknown") == strategy
                    ]),
                }
                for strategy in strategies
            },
        }
    return out


def _slot_conflict_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("plan_status") == "selected_by_entry_plan":
            selected_by_date[str(row.get("candidate_date"))].append(row)

    comparisons = []
    for row in rows:
        if row.get("plan_status") not in {"slot_sliced", "scarce_slot_breakout_deferred"}:
            continue
        selected = selected_by_date.get(str(row.get("candidate_date"))) or []
        selected_rets = [
            item.get("ret_20d")
            for item in selected
            if isinstance(item.get("ret_20d"), (int, float))
        ]
        candidate_ret = row.get("ret_20d")
        if not selected_rets or not isinstance(candidate_ret, (int, float)):
            continue
        selected_avg = mean([float(value) for value in selected_rets])
        delta = float(candidate_ret) - selected_avg
        comparisons.append(
            {
                "window": row.get("window"),
                "candidate_date": row.get("candidate_date"),
                "ticker": row.get("ticker"),
                "strategy": row.get("strategy"),
                "plan_status": row.get("plan_status"),
                "filing_shock_tag": row.get("filing_shock_tag"),
                "candidate_ret_20d": round(float(candidate_ret), 6),
                "same_day_selected_avg_ret_20d": round(selected_avg, 6),
                "slot_conflict_delta_20d": round(delta, 6),
            }
        )
    by_tag = {}
    for tag in sorted({row["filing_shock_tag"] for row in comparisons}):
        subset = [row for row in comparisons if row["filing_shock_tag"] == tag]
        by_tag[tag] = {
            "count": len(subset),
            "delta_20d_distribution": _summarize_values([
                row["slot_conflict_delta_20d"] for row in subset
            ]),
            "positive_delta_count": sum(
                1 for row in subset if row["slot_conflict_delta_20d"] > 0
            ),
        }
    return {
        "same_day_comparable_count": len(comparisons),
        "overall_delta_20d_distribution": _summarize_values([
            row["slot_conflict_delta_20d"] for row in comparisons
        ]),
        "by_tag": by_tag,
        "examples": comparisons[:40],
    }


def _shadow_event_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_fields = (
        "event_date",
        "usable_trade_date",
        "form_type",
        "accepted_datetime",
        "fiscal_period_end",
        "eps_surprise",
        "revenue_surprise",
        "gross_margin_delta",
        "fcf_to_net_income_gap",
        "inventory_growth",
        "receivables_growth",
        "guidance_raise_cut",
        "eight_k_item_type",
        "data_source",
        "pit_safe",
    )
    out = []
    for row in rows:
        filing = row.get("recent_filing") or {}
        item = {
            "window": row.get("window"),
            "candidate_date": row.get("candidate_date"),
            "ticker": row.get("ticker"),
            "strategy": row.get("strategy"),
            "plan_status": row.get("plan_status"),
            "filing_shock_tag": row.get("filing_shock_tag"),
            "recent_filing_distance_trading_days": row.get(
                "recent_filing_distance_trading_days"
            ),
            "positive_evidence_fields": row.get("positive_evidence_fields"),
            "negative_evidence_fields": row.get("negative_evidence_fields"),
            "classification_reason": row.get("classification_reason"),
            "ret_5d": row.get("ret_5d"),
            "ret_10d": row.get("ret_10d"),
            "ret_20d": row.get("ret_20d"),
            "ret_60d": row.get("ret_60d"),
        }
        for field in event_fields:
            item[field] = filing.get(field)
        out.append(item)
    return out


def _metric_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "total_pnl": result.get("total_pnl"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct", benchmarks.get("vs_spy_pct")),
        "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct", benchmarks.get("vs_qqq_pct")),
    }


def _field_availability_summary(sec_features: list[dict[str, Any]]) -> dict[str, Any]:
    availability = Counter()
    gap_reasons = Counter()
    directional_rows = 0
    for row in sec_features:
        for field, state in (row.get("field_availability") or {}).items():
            availability[f"{field}:{state}"] += 1
        for reason in row.get("gap_reasons") or []:
            gap_reasons[str(reason)] += 1
        pos, neg, _, _ = _directional_field_counts(row)
        directional_rows += int(bool(pos or neg))
    return {
        "sec_feature_rows": len(sec_features),
        "pit_safe_rows": sum(1 for row in sec_features if row.get("pit_safe")),
        "pit_safe_fraction": _safe_ratio(
            sum(1 for row in sec_features if row.get("pit_safe")),
            len(sec_features),
        ),
        "directional_financial_shock_rows": directional_rows,
        "field_availability_top": dict(availability.most_common(30)),
        "gap_reasons_top": dict(gap_reasons.most_common(20)),
    }


def _window_summary(
    *,
    result: dict[str, Any],
    rows: list[dict[str, Any]],
    coverage_report: dict[str, Any],
) -> dict[str, Any]:
    plan_counts = Counter(str(row.get("plan_status") or "unknown") for row in rows)
    tag_counts = Counter(str(row.get("filing_shock_tag") or "unknown") for row in rows)
    recent_rows = [
        row for row in rows
        if row.get("filing_shock_tag") != "A_no_recent_filing_event"
    ]
    return {
        "baseline_metrics": _metric_snapshot(result),
        "coverage": result.get("non_ohlcv_coverage"),
        "coverage_report_decision": coverage_report.get("decision"),
        "coverage_report_complete_fraction": coverage_report.get("complete_fraction"),
        "candidate_count": len(rows),
        "plan_status_counts": dict(plan_counts),
        "filing_shock_tag_counts": dict(tag_counts),
        "candidates_with_recent_filing": len(recent_rows),
        "recent_filing_candidate_rate": _safe_ratio(len(recent_rows), len(rows)),
        "selected_candidate_count": plan_counts.get("selected_by_entry_plan", 0),
        "selected_candidates_with_recent_filing": sum(
            1 for row in rows
            if row.get("plan_status") == "selected_by_entry_plan"
            and row.get("filing_shock_tag") != "A_no_recent_filing_event"
        ),
        "actual_entered_count": (
            result.get("entry_execution_attribution") or {}
        ).get("entered_count"),
        "forward_returns_by_tag": _tag_strategy_summary(rows),
        "candidate_overlap_with_existing_signals": {
            "selected_by_entry_plan_rows": plan_counts.get("selected_by_entry_plan", 0),
            "selected_with_recent_filing": sum(
                1 for row in rows
                if row.get("plan_status") == "selected_by_entry_plan"
                and row.get("filing_shock_tag") != "A_no_recent_filing_event"
            ),
            "selected_recent_filing_rate": _safe_ratio(
                sum(
                    1 for row in rows
                    if row.get("plan_status") == "selected_by_entry_plan"
                    and row.get("filing_shock_tag") != "A_no_recent_filing_event"
                ),
                plan_counts.get("selected_by_entry_plan", 0),
            ),
            "earnings_event_long_candidate_count": sum(
                1 for row in rows if row.get("strategy") == "earnings_event_long"
            ),
            "earnings_event_long_recent_filing_count": sum(
                1 for row in rows
                if row.get("strategy") == "earnings_event_long"
                and row.get("filing_shock_tag") != "A_no_recent_filing_event"
            ),
            "breakout_long_candidate_count": sum(
                1 for row in rows if row.get("strategy") == "breakout_long"
            ),
            "breakout_long_recent_filing_count": sum(
                1 for row in rows
                if row.get("strategy") == "breakout_long"
                and row.get("filing_shock_tag") != "A_no_recent_filing_event"
            ),
        },
        "scarce_slot_opportunity_cost": _slot_conflict_summary(rows),
        "sample_candidate_rows": rows[:40],
    }


def _run_window(name: str, spec: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    snapshot = _load_snapshot(REPO_ROOT / spec["snapshot"])
    sec_features = _load_sec_features(spec["start"], spec["end"])
    events_by_ticker = _build_events_by_ticker(sec_features)
    captured: list[dict[str, Any]] = []
    original_plan = _capture_plan_candidates(
        window_name=name,
        events_by_ticker=events_by_ticker,
        snapshot=snapshot,
        captured=captured,
    )
    try:
        result = BacktestEngine(
            sorted(get_universe()),
            start=spec["start"],
            end=spec["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / spec["snapshot"]),
            require_non_ohlcv=True,
            replay_llm=False,
            replay_news=False,
            include_pilot_sleeve=False,
        ).run()
    finally:
        bt.plan_entry_candidates = original_plan
    if "error" in result:
        raise RuntimeError(f"{name} failed: {result['error']}")
    return result, captured, sec_features


def _append_or_replace_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") == record.get("experiment_id"):
                continue
            lines.append(json.dumps(existing, ensure_ascii=False, sort_keys=True))
    lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_markdown(payload: dict[str, Any]) -> None:
    def fmt_return(horizon_row: dict[str, Any]) -> str:
        if not horizon_row or horizon_row.get("count", 0) == 0:
            return "n=0"
        return "n={count}, avg={avg:.2f}%, med={median:.2f}%, win={win:.1f}%".format(
            count=horizon_row["count"],
            avg=horizon_row["avg_pct"],
            median=horizon_row["median_pct"],
            win=horizon_row["win_rate"] * 100,
        )

    lines = [
        f"# {EXPERIMENT_ID}: Candidate Filing-Shock Shadow Tags",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Coverage Table",
        "",
        "| Window | Candidates | Recent filing | Selected | Selected recent | Complete fraction |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in payload["shadow_metrics"]["by_window"].items():
        lines.append(
            "| {name} | {candidates} | {recent} | {selected} | {selected_recent} | {coverage} |".format(
                name=name,
                candidates=row["candidate_count"],
                recent=row["candidates_with_recent_filing"],
                selected=row["selected_candidate_count"],
                selected_recent=row["selected_candidates_with_recent_filing"],
                coverage=row["coverage_report_complete_fraction"],
            )
        )
    lines.extend(
        [
            "",
            "## Data Availability",
            "",
            "- SEC accepted/usable trade timestamps are complete in the canonical replay artifacts.",
            "- Directional EPS/revenue surprise and guidance fields remain missing without a PIT consensus/guidance source.",
            "- Recent filing context mostly acts as an event-presence tag, not a true positive/negative financial-shock grade.",
            "",
            "## Tagged Candidate Forward Returns",
            "",
            "| Tag | Candidates | 5d | 10d | 20d | 60d |",
            "| --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for tag, tag_row in payload["shadow_metrics"]["aggregate"]["forward_returns_by_tag"].items():
        returns = tag_row["forward_returns"]
        lines.append(
            "| {tag} | {count} | {ret_5d} | {ret_10d} | {ret_20d} | {ret_60d} |".format(
                tag=tag,
                count=tag_row["candidate_count"],
                ret_5d=fmt_return(returns["5d"]),
                ret_10d=fmt_return(returns["10d"]),
                ret_20d=fmt_return(returns["20d"]),
                ret_60d=fmt_return(returns["60d"]),
            )
        )
    lines.extend(
        [
            "",
            "## Slot Value",
            "",
            json.dumps(payload["candidate_overlap_and_slot_value"], indent=2, ensure_ascii=False),
            "",
            "## Next Action",
            "",
            payload["next_action"],
            "",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def _sync_registry(ticket: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON) if REGISTRY_JSON.exists() else {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
    }
    experiments = registry.setdefault("experiments", [])

    exp003 = {
        "experiment_id": "exp-20260507-003",
        "status": "rejected",
        "lane": "alpha_search",
        "owner": "alpha-discovery",
        "hypothesis": "If a `breakout_long` candidate has a PIT-safe SEC filing within the last 20 trading days, the event context may confirm the technical breakout and justify a larger risk budget.",
        "ticket_file": "docs/experiments/tickets/exp-20260507-003.json",
        "updated_at": "2026-05-07T01:18:21+00:00",
    }
    exp004 = {
        "experiment_id": ticket["experiment_id"],
        "status": ticket["status"],
        "lane": ticket["lane"],
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": "docs/experiments/tickets/exp-20260507-004.json",
        "updated_at": _utc_now_iso(),
    }
    by_id = {
        row.get("experiment_id"): row
        for row in experiments
        if row.get("experiment_id") not in {"exp-20260507-003", "exp-20260507-004"}
    }
    by_id["exp-20260507-003"] = exp003
    by_id["exp-20260507-004"] = exp004
    registry["experiments"] = list(by_id.values())
    registry["updated_at"] = exp004["updated_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> int:
    ticket = _load_json(TICKET_JSON)
    timestamp = _utc_now_iso()
    by_window: dict[str, Any] = OrderedDict()
    all_candidate_rows: list[dict[str, Any]] = []
    all_sec_features: list[dict[str, Any]] = []

    for name, spec in WINDOWS.items():
        result, candidate_rows, sec_features = _run_window(name, spec)
        coverage_report = _load_json(REPO_ROOT / spec["coverage_report"])
        by_window[name] = _window_summary(
            result=result,
            rows=candidate_rows,
            coverage_report=coverage_report,
        )
        all_candidate_rows.extend(candidate_rows)
        all_sec_features.extend(sec_features)

    aggregate_baseline = {
        "expected_value_score_sum": _round(sum(
            row["baseline_metrics"]["expected_value_score"] or 0.0
            for row in by_window.values()
        ), 4),
        "total_pnl_sum": _round(sum(
            row["baseline_metrics"]["total_pnl"] or 0.0
            for row in by_window.values()
        ), 2),
        "trade_count_sum": sum(
            int(row["baseline_metrics"]["trade_count"] or 0)
            for row in by_window.values()
        ),
        "signals_generated_sum": sum(
            int(row["baseline_metrics"]["signals_generated"] or 0)
            for row in by_window.values()
        ),
        "signals_survived_sum": sum(
            int(row["baseline_metrics"]["signals_survived"] or 0)
            for row in by_window.values()
        ),
    }

    aggregate_candidates = {
        "candidate_count": len(all_candidate_rows),
        "plan_status_counts": dict(Counter(
            str(row.get("plan_status")) for row in all_candidate_rows
        )),
        "filing_shock_tag_counts": dict(Counter(
            str(row.get("filing_shock_tag")) for row in all_candidate_rows
        )),
        "forward_returns_by_tag": _tag_strategy_summary(all_candidate_rows),
        "field_availability": _field_availability_summary(all_sec_features),
    }
    slot_value = _slot_conflict_summary(all_candidate_rows)
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "parity_test_added": False,
        "replay_only": True,
        "alters_orders": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "production_signal_path_changed": False,
    }
    decision = "shadow_only"
    next_action = (
        "Do not promote a filing-presence sizing rule; exp-20260507-003 already failed. "
        "The next valid SEC/earnings step needs a richer event-quality discriminator "
        "with directional PIT fields or closed forward paper outcomes."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_discovery",
        "change_type": "shadow_candidate_tagging",
        "hypothesis": ticket["hypothesis"],
        "non_ohlcv_data_source": "SEC filing features, SEC accepted metadata/text, existing earnings snapshots, canonical OHLCV snapshots for forward returns",
        "mechanism_family": "earnings_sec_filing_shock_event_confirmation_overlay",
        "single_causal_variable": ticket["single_causal_variable"],
        "historical_experiment_check": {
            "exp-20260418-004": "C strategy was damaged by missing earnings fields and poor win rate.",
            "exp-20260506-001": "Fresh SEC/earnings audit found missing financial shock fields and no closed outcomes.",
            "exp-20260507-002": "Canonical replay coverage is complete; next action was candidate-row tagging.",
            "exp-20260507-003": "Recent SEC filing breakout sizing failed Gate 4; do not retry nearby filing-presence risk multipliers.",
            "playbook": "SEC/earnings filing shock is high-priority only as auditable event confirmation or C grading, not raw SEC threshold sweeping.",
        },
        "mechanism_insight_check": {
            "recent_insight_ban_hit": False,
            "why_not_repeat": "This is not another risk multiplier or threshold replay. It persists and audits candidate tags only.",
            "priority_change": "exp-20260507-002 moved the blocker from replay coverage to candidate-row attribution.",
        },
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}"
            for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "data_availability_pit_status": {
            "coverage_complete_all_windows": all(
                row["coverage_report_complete_fraction"] == 1.0
                for row in by_window.values()
            ),
            "sec_rows_pit_safe_fraction": aggregate_candidates["field_availability"]["pit_safe_fraction"],
            "directional_financial_shock_rows": aggregate_candidates["field_availability"]["directional_financial_shock_rows"],
            "pit_caveats": [
                "SEC accepted_datetime and usable_trade_date are replayable PIT proxies.",
                "Backfilled SEC public timestamps do not prove the local production job observed the filing intraday.",
                "EPS/revenue surprise and structured guidance fields remain missing without PIT consensus/guidance archives.",
                "Historical earnings snapshots are replayable repo artifacts but not vendor-grade consensus truth.",
            ],
        },
        "baseline_metrics": {
            "by_window": {
                name: row["baseline_metrics"] for name, row in by_window.items()
            },
            "aggregate": aggregate_baseline,
        },
        "shadow_metrics": {
            "tag_definitions": {
                "A_no_recent_filing_event": "No PIT-safe SEC filing within 20 trading days before/on candidate date.",
                "B_positive_filing_shock": "Recent PIT-safe filing with positive same-row directional financial evidence and no negative directional field.",
                "C_negative_filing_shock": "Recent PIT-safe filing with negative same-row directional financial evidence and no positive directional field.",
                "D_unclear_or_missing_data": "Recent filing exists but directional fields are missing or mixed.",
            },
            "aggregate": aggregate_candidates,
            "by_window": by_window,
        },
        "expected_value_score_delta": 0.0,
        "delta_metrics": {
            "strategy_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "reason": "Shadow-only candidate tagging; no trading policy changed.",
        },
        "candidate_overlap_and_slot_value": {
            "candidate_count": len(all_candidate_rows),
            "overlap_with_existing_signals": {
                "selected_by_entry_plan_rows": sum(
                    1 for row in all_candidate_rows
                    if row.get("plan_status") == "selected_by_entry_plan"
                ),
                "selected_with_recent_filing": sum(
                    1 for row in all_candidate_rows
                    if row.get("plan_status") == "selected_by_entry_plan"
                    and row.get("filing_shock_tag") != "A_no_recent_filing_event"
                ),
            },
            "scarce_slot_opportunity_cost": slot_value,
        },
        "candidate_rows": all_candidate_rows,
        "shadow_event_table": _shadow_event_table(all_candidate_rows),
        "production_impact": production_impact,
        "decision": decision,
        "status": "observed_only",
        "next_action": next_action,
        "risk_notes": [
            "Candidate capture uses experiment-only monkeypatching of backtester.plan_entry_candidates and restores it after each window.",
            "This does not make candidate-row persistence available in production; promotion would require a shared explicit adapter.",
            "Directional filing-shock tags are mostly data-limited because same-accession financial fields are sparse or missing.",
        ],
        "related_files": [
            "quant/experiments/exp_20260507_004_candidate_filing_shock_shadow.py",
            "data/experiments/exp-20260507-004/exp_20260507_004_candidate_filing_shock_shadow.json",
            "docs/experiments/tickets/exp-20260507-004.json",
            "docs/experiments/logs/exp-20260507-004.json",
            "docs/experiments/artifacts/exp-20260507-004_candidate_filing_shock_shadow.md",
            "docs/non_ohlcv_data_audit/sec_earnings_filing_shock_candidate_tags_exp-20260507-004_20260507.md",
            "docs/experiment_log.jsonl",
        ],
    }

    ticket["status"] = "observed_only"
    ticket["completed_at"] = timestamp
    ticket["result"] = {
        "decision": decision,
        "candidate_count": len(all_candidate_rows),
        "expected_value_score_delta": 0.0,
        "production_impact": production_impact,
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_json(TICKET_JSON, ticket)
    _write_markdown(payload)
    _sync_registry(ticket)
    _append_or_replace_jsonl(
        EXPERIMENT_LOG,
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "status": payload["status"],
            "decision": decision,
            "lane": payload["lane"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "hypothesis": payload["hypothesis"],
            "single_causal_variable": payload["single_causal_variable"],
            "non_ohlcv_data_source": payload["non_ohlcv_data_source"],
            "date_range": payload["date_range"],
            "market_regime_summary": payload["market_regime_summary"],
            "baseline_metrics": payload["baseline_metrics"],
            "shadow_metrics_reference": {
                "aggregate_candidate_count": len(all_candidate_rows),
                "tag_counts": aggregate_candidates["filing_shock_tag_counts"],
                "slot_conflict_comparable_count": slot_value["same_day_comparable_count"],
                "field_availability": aggregate_candidates["field_availability"],
            },
            "expected_value_score_delta": 0.0,
            "production_impact": production_impact,
            "historical_experiment_check": payload["historical_experiment_check"],
            "next_action": next_action,
            "related_files": payload["related_files"],
        },
    )
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "candidate_count": len(all_candidate_rows),
        "tag_counts": aggregate_candidates["filing_shock_tag_counts"],
        "slot_conflict_comparable_count": slot_value["same_day_comparable_count"],
        "outputs": payload["related_files"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
