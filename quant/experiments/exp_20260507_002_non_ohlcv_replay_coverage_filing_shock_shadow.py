"""exp-20260507-002 non-OHLCV replay coverage and filing-shock shadow audit.

This is a measurement-repair and shadow-tagging experiment. It proves that the
canonical non-OHLCV replay artifacts are complete before computing any SEC /
earnings / filing-shock labels. It does not change signal generation, ranking,
sizing, exits, orders, or production adapters.
"""

from __future__ import annotations

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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260507-002"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "non_ohlcv_replay_coverage_filing_shock_shadow.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_earnings_filing_shock_replay_coverage_exp-20260507-002_20260507.md"
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "coverage_report": "data/non_ohlcv/backtest_coverage_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "coverage_report": "data/non_ohlcv/backtest_coverage_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "coverage_report": "data/non_ohlcv/backtest_coverage_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

HORIZONS = (5, 10, 20, 60)
RECENT_FILING_LOOKBACK_TRADING_DAYS = 20
ROUND_TRIP_COST = 0.0035


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        out = float(value)
        if math.isfinite(out):
            return out
    if isinstance(value, str) and value.strip():
        try:
            out = float(value)
        except ValueError:
            return None
        return out if math.isfinite(out) else None
    return None


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    raw = payload.get("ohlcv") or payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in raw.items():
        converted = []
        for row in rows or []:
            date = str(row.get("Date") or row.get("date") or "")[:10]
            close = _as_float(row.get("Close") if "Close" in row else row.get("close"))
            if not date or close is None:
                continue
            converted.append({
                "date": date,
                "close": close,
            })
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
    horizons: tuple[int, ...] = HORIZONS,
) -> dict[str, Any]:
    rows = snapshot.get(ticker.upper()) or []
    start_idx = _idx_on_or_after(rows, date_value)
    if start_idx is None:
        return {f"ret_{h}d": None for h in horizons} | {"base_date": None, "base_close": None}
    base = _as_float(rows[start_idx].get("close"))
    out = {"base_date": rows[start_idx]["date"], "base_close": base}
    for horizon in horizons:
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


def _pct(value: Any) -> float | None:
    numeric = _as_float(value)
    if numeric is None:
        return None
    return numeric


def _directional_field_counts(row: dict[str, Any]) -> tuple[int, int, list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    numeric_fields = [
        "eps_surprise",
        "revenue_surprise",
        "gross_margin_delta",
        "fcf_to_net_income_gap",
    ]
    for field in numeric_fields:
        value = _pct(row.get(field))
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
        tag = "B_positive_filing_shock"
        reason = "positive directional same-row financial evidence"
    elif negative_count > 0 and positive_count == 0:
        tag = "C_negative_filing_shock"
        reason = "negative directional same-row financial evidence"
    else:
        tag = "D_unclear_or_missing_data"
        reason = (
            "SEC event exists but directional financial shock fields are missing or mixed"
        )
    return {
        "filing_shock_tag": tag,
        "positive_evidence_fields": positive_fields,
        "negative_evidence_fields": negative_fields,
        "classification_reason": reason,
    }


def _date_from_feature_file(path: Path) -> str | None:
    stem = path.stem
    suffix = stem.rsplit("_", 1)[-1]
    if len(suffix) != 8 or not suffix.isdigit():
        return None
    return f"{suffix[:4]}-{suffix[4:6]}-{suffix[6:]}"


def _load_sec_features(start: str, end: str, lookback_calendar_days: int = 45) -> list[dict[str, Any]]:
    min_date = (datetime.fromisoformat(start) - timedelta(days=lookback_calendar_days)).date().isoformat()
    max_date = end
    rows: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_features_*.jsonl")):
        file_date = _date_from_feature_file(path)
        if not file_date or file_date < min_date or file_date > max_date:
            continue
        for row in _load_jsonl(path):
            accepted = row.get("accepted_datetime") or row.get("accepted_at")
            usable = row.get("usable_trade_date")
            if not accepted or not usable:
                row["pit_safe"] = False
            row["ticker"] = str(row.get("ticker") or "").upper()
            if row.get("ticker"):
                rows.append(row)
    return rows


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
        if not row.get("pit_safe", False):
            continue
        distance = _market_trading_day_distance(snapshot, usable, date_value)
        if distance is None or distance < 0 or distance > RECENT_FILING_LOOKBACK_TRADING_DAYS:
            continue
        if best is None or distance < (best_distance or 10**9):
            best = row
            best_distance = distance
    return best, best_distance


def _summarize_values(values: list[float]) -> dict[str, Any]:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
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
        "win_rate": round(sum(1 for v in clean if v > 0) / len(clean), 4),
        "best_pct": round(max(clean) * 100.0, 4),
        "worst_pct": round(min(clean) * 100.0, 4),
    }


def _summarize_forward_by_tag(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tag in [
        "A_no_recent_filing_event",
        "B_positive_filing_shock",
        "C_negative_filing_shock",
        "D_unclear_or_missing_data",
    ]:
        subset = [row for row in rows if row.get("filing_shock_tag") == tag]
        out[tag] = {
            "candidate_count": len(subset),
            "by_horizon": {
                f"{horizon}d": _summarize_values([
                    row.get(f"ret_{horizon}d") for row in subset
                ])
                for horizon in HORIZONS
            },
        }
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


def _candidate_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("ticker") or "").upper(),
        str(row.get("candidate_date") or row.get("entry_date") or "")[:10],
        str(row.get("strategy") or ""),
    )


def _build_window_shadow(
    window_name: str,
    window: dict[str, str],
    result: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    sec_features: list[dict[str, Any]],
) -> dict[str, Any]:
    events_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sec_features:
        ticker = row.get("ticker")
        usable = str(row.get("usable_trade_date") or "")[:10]
        if ticker and usable <= window["end"]:
            events_by_ticker[str(ticker).upper()].append(row)
    for ticker in events_by_ticker:
        events_by_ticker[ticker].sort(
            key=lambda item: (
                str(item.get("usable_trade_date") or ""),
                str(item.get("accepted_datetime") or ""),
            ),
            reverse=True,
        )

    selected_rows: list[dict[str, Any]] = []
    for trade in result.get("trades") or []:
        ticker = str(trade.get("ticker") or "").upper()
        entry_date = str(trade.get("entry_date") or "")[:10]
        event, distance = _latest_recent_event(events_by_ticker, snapshot, ticker, entry_date)
        classification = _classify_filing_shock(event)
        returns = _forward_returns(snapshot, ticker, entry_date)
        selected_rows.append({
            "window": window_name,
            "candidate_type": "selected_signal",
            "ticker": ticker,
            "strategy": trade.get("strategy"),
            "candidate_date": entry_date,
            "entry_date": entry_date,
            "pnl": trade.get("pnl"),
            "pnl_pct_net": trade.get("pnl_pct_net"),
            "recent_filing_lookback_trading_days": RECENT_FILING_LOOKBACK_TRADING_DAYS,
            "recent_filing_distance_trading_days": distance,
            "recent_filing": _event_reference(event),
            **classification,
            **returns,
        })

    deferred_rows: list[dict[str, Any]] = []
    for event_row in ((result.get("scarce_slot_attribution") or {}).get("deferred_events") or []):
        ticker = str(event_row.get("ticker") or "").upper()
        date_value = str(event_row.get("date") or "")[:10]
        event, distance = _latest_recent_event(events_by_ticker, snapshot, ticker, date_value)
        classification = _classify_filing_shock(event)
        returns = _forward_returns(snapshot, ticker, date_value)
        deferred_rows.append({
            "window": window_name,
            "candidate_type": "scarce_slot_deferred",
            "ticker": ticker,
            "strategy": event_row.get("strategy"),
            "candidate_date": date_value,
            "trade_quality_score": event_row.get("trade_quality_score"),
            "confidence_score": event_row.get("confidence_score"),
            "available_slots": event_row.get("available_slots"),
            "recent_filing_lookback_trading_days": RECENT_FILING_LOOKBACK_TRADING_DAYS,
            "recent_filing_distance_trading_days": distance,
            "recent_filing": _event_reference(event),
            **classification,
            **returns,
        })

    selected_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected_rows:
        selected_by_date[str(row.get("candidate_date"))].append(row)
    slot_deltas: list[float] = []
    slot_rows = []
    for row in deferred_rows:
        comparable = selected_by_date.get(str(row.get("candidate_date"))) or []
        selected_20d = [
            item.get("ret_20d")
            for item in comparable
            if isinstance(item.get("ret_20d"), (int, float))
        ]
        deferred_20d = row.get("ret_20d")
        if not selected_20d or not isinstance(deferred_20d, (int, float)):
            continue
        delta = float(deferred_20d) - mean(selected_20d)
        slot_deltas.append(delta)
        slot_rows.append({
            "date": row.get("candidate_date"),
            "ticker": row.get("ticker"),
            "tag": row.get("filing_shock_tag"),
            "deferred_20d_return": round(float(deferred_20d), 6),
            "same_day_selected_avg_20d_return": round(mean(selected_20d), 6),
            "slot_conflict_delta_20d": round(delta, 6),
        })

    event_candidates = _build_event_candidate_rows(
        window_name,
        window,
        snapshot,
        sec_features,
        selected_rows,
    )

    return {
        "window": window_name,
        "coverage": result.get("non_ohlcv_coverage"),
        "baseline_metrics": _metric_snapshot(result),
        "selected_signal_count": len(selected_rows),
        "scarce_slot_deferred_count": len(deferred_rows),
        "event_candidate_count": len(event_candidates),
        "selected_signal_forward_returns_by_tag": _summarize_forward_by_tag(selected_rows),
        "scarce_slot_deferred_forward_returns_by_tag": _summarize_forward_by_tag(deferred_rows),
        "filing_event_candidate_forward_returns_by_tag": _summarize_forward_by_tag(event_candidates),
        "candidate_overlap": {
            "selected_signals_with_recent_filing": sum(
                1 for row in selected_rows
                if row.get("filing_shock_tag") != "A_no_recent_filing_event"
            ),
            "selected_signal_overlap_rate": _safe_ratio(
                sum(
                    1 for row in selected_rows
                    if row.get("filing_shock_tag") != "A_no_recent_filing_event"
                ),
                len(selected_rows),
            ),
            "deferred_slot_candidates_with_recent_filing": sum(
                1 for row in deferred_rows
                if row.get("filing_shock_tag") != "A_no_recent_filing_event"
            ),
            "event_candidates_overlapping_selected_same_ticker_same_day": sum(
                1 for row in event_candidates if row.get("overlaps_selected_same_ticker_same_day")
            ),
            "event_candidates_overlapping_selected_same_ticker_within_20td": sum(
                1 for row in event_candidates
                if row.get("overlaps_selected_same_ticker_within_20td")
            ),
        },
        "scarce_slot_opportunity_cost": {
            "same_day_comparable_count": len(slot_deltas),
            "distribution_vs_same_day_selected_avg_20d": _summarize_values(slot_deltas),
            "examples": slot_rows[:20],
            "caveat": (
                "Only scarce_slot_deferred events are persisted by the backtester; "
                "full pre-ranking candidate rows are not yet available."
            ),
        },
        "rows": {
            "selected_signals": selected_rows,
            "scarce_slot_deferred": deferred_rows,
            "filing_event_candidates": event_candidates,
        },
    }


def _event_reference(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    return {
        "ticker": event.get("ticker"),
        "form_type": event.get("form_type"),
        "accepted_datetime": event.get("accepted_datetime") or event.get("accepted_at"),
        "usable_trade_date": event.get("usable_trade_date"),
        "source_accession": event.get("source_accession") or event.get("accession_number"),
        "eight_k_item_type": event.get("eight_k_item_type"),
        "pit_safe": event.get("pit_safe"),
        "field_availability": event.get("field_availability"),
        "gap_reasons": event.get("gap_reasons"),
    }


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _build_event_candidate_rows(
    window_name: str,
    window: dict[str, str],
    snapshot: dict[str, list[dict[str, Any]]],
    sec_features: list[dict[str, Any]],
    selected_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_keys_same_day = {
        (row["ticker"], row["candidate_date"])
        for row in selected_rows
    }
    selected_by_ticker = defaultdict(list)
    for row in selected_rows:
        selected_by_ticker[row["ticker"]].append(row["candidate_date"])

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in sec_features:
        usable = str(event.get("usable_trade_date") or "")[:10]
        ticker = str(event.get("ticker") or "").upper()
        accession = str(event.get("source_accession") or "")
        if not ticker or not usable or usable < window["start"] or usable > window["end"]:
            continue
        if not event.get("pit_safe", False):
            continue
        key = (ticker, usable, accession)
        if key in seen:
            continue
        seen.add(key)
        classification = _classify_filing_shock(event)
        returns = _forward_returns(snapshot, ticker, usable)
        within_20 = False
        for selected_date in selected_by_ticker.get(ticker, []):
            distance = _market_trading_day_distance(snapshot, usable, selected_date)
            if distance is not None and 0 <= distance <= RECENT_FILING_LOOKBACK_TRADING_DAYS:
                within_20 = True
                break
        out.append({
            "window": window_name,
            "candidate_type": "filing_event_candidate",
            "ticker": ticker,
            "candidate_date": usable,
            "form_type": event.get("form_type"),
            "eight_k_item_type": event.get("eight_k_item_type"),
            "source_accession": accession,
            "accepted_datetime": event.get("accepted_datetime"),
            "pit_safe": event.get("pit_safe"),
            "field_availability": event.get("field_availability"),
            "gap_reasons": event.get("gap_reasons"),
            "overlaps_selected_same_ticker_same_day": (ticker, usable) in selected_keys_same_day,
            "overlaps_selected_same_ticker_within_20td": within_20,
            **classification,
            **returns,
        })
    return out


def _field_availability_summary(sec_features: list[dict[str, Any]]) -> dict[str, Any]:
    row_count = len(sec_features)
    pit_safe = sum(1 for row in sec_features if row.get("pit_safe", False))
    availability = Counter()
    missing_reasons = Counter()
    directional_rows = 0
    for row in sec_features:
        fields = row.get("field_availability") or {}
        for field, status in fields.items():
            availability[f"{field}:{status}"] += 1
        for reason in row.get("gap_reasons") or []:
            missing_reasons[str(reason)] += 1
        pos, neg, _, _ = _directional_field_counts(row)
        if pos or neg:
            directional_rows += 1
    return {
        "sec_feature_rows": row_count,
        "pit_safe_rows": pit_safe,
        "pit_safe_fraction": _safe_ratio(pit_safe, row_count),
        "directional_financial_shock_rows": directional_rows,
        "field_availability_top": dict(availability.most_common(20)),
        "gap_reasons_top": dict(missing_reasons.most_common(20)),
    }


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
            lines.append(json.dumps(existing, ensure_ascii=False))
    lines.append(json.dumps(record, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_ticket(ticket: dict[str, Any], result_summary: dict[str, Any]) -> dict[str, Any]:
    ticket["status"] = "observed_only"
    ticket["completed_at"] = _utc_now_iso()
    ticket["result"] = result_summary
    _write_json(TICKET_JSON, ticket)
    return ticket


def _update_registry(ticket: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON) if REGISTRY_JSON.exists() else {
        "schema_version": 1,
        "updated_at": None,
        "experiments": [],
    }
    entry = {
        "experiment_id": ticket["experiment_id"],
        "status": ticket["status"],
        "lane": ticket["lane"],
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": "experiments/tickets/exp-20260507-002.json",
        "updated_at": _utc_now_iso(),
    }
    experiments = registry.setdefault("experiments", [])
    for idx, existing in enumerate(experiments):
        if existing.get("experiment_id") == EXPERIMENT_ID:
            experiments[idx] = {**existing, **entry}
            break
    else:
        experiments.append(entry)
    registry["updated_at"] = entry["updated_at"]
    _write_json(REGISTRY_JSON, registry)


def _write_audit_markdown(payload: dict[str, Any]) -> None:
    coverage = payload["coverage_summary"]
    shadow = payload["shadow_summary"]
    lines = [
        f"# SEC / Earnings / Filing-Shock Replay Coverage Audit ({EXPERIMENT_ID})",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Data Source",
        "Public SEC accepted filing metadata/text/features plus existing repo earnings snapshots. SEC tradability uses accepted_datetime -> usable_trade_date only.",
        "",
        "## PIT Status",
        f"- Three-window coverage complete: {coverage['all_windows_complete']}",
        f"- PIT caveats: {', '.join(payload['pit_caveats'])}",
        "",
        "## Coverage Table",
        "| window | dates | complete_fraction | complete_days | business_days | missing_by_artifact | biased_days |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for name, row in coverage["by_window"].items():
        cov = row["backtester_non_ohlcv_coverage"]
        lines.append(
            "| {name} | {start}..{end} | {frac} | {complete_days} | {business_days} | {missing} | {biased} |".format(
                name=name,
                start=row["start"],
                end=row["end"],
                frac=cov.get("complete_fraction"),
                complete_days=cov.get("complete_days"),
                business_days=cov.get("business_days"),
                missing=json.dumps(cov.get("missing_by_artifact") or {}, ensure_ascii=False),
                biased=cov.get("biased_days"),
            )
        )
    lines.extend([
        "",
        "## Shadow Tagging Summary",
        "| window | selected signals | selected with recent filing | filing event candidates | deferred slot candidates | slot comparables |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for name, row in shadow["by_window"].items():
        overlap = row["candidate_overlap"]
        lines.append(
            "| {name} | {selected} | {recent} | {events} | {deferred} | {slot} |".format(
                name=name,
                selected=row["selected_signal_count"],
                recent=overlap["selected_signals_with_recent_filing"],
                events=row["event_candidate_count"],
                deferred=row["scarce_slot_deferred_count"],
                slot=row["scarce_slot_opportunity_cost"]["same_day_comparable_count"],
            )
        )
    lines.extend([
        "",
        "## Decision",
        payload["decision"],
        "",
        "## Next Action",
        payload["next_action"],
        "",
    ])
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ticket = _load_json(TICKET_JSON)
    universe = get_universe()

    baseline_metrics: dict[str, Any] = {}
    coverage_by_window: dict[str, Any] = {}
    shadow_by_window: dict[str, Any] = {}
    sec_features_all: list[dict[str, Any]] = []

    for name, window in WINDOWS.items():
        engine = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
            require_non_ohlcv=True,
        )
        result = engine.run()
        if "error" in result:
            raise RuntimeError(f"{name} require-non-OHLCV failed: {result['error']}")

        snapshot = _load_snapshot(REPO_ROOT / window["snapshot"])
        sec_features = _load_sec_features(window["start"], window["end"])
        sec_features_all.extend(sec_features)
        shadow = _build_window_shadow(name, window, result, snapshot, sec_features)
        baseline_metrics[name] = _metric_snapshot(result)
        coverage_report = _load_json(REPO_ROOT / window["coverage_report"])
        coverage_by_window[name] = {
            "start": window["start"],
            "end": window["end"],
            "coverage_report": window["coverage_report"],
            "coverage_report_decision": coverage_report.get("decision"),
            "coverage_report_complete_fraction": coverage_report.get("complete_fraction"),
            "backtester_non_ohlcv_coverage": result.get("non_ohlcv_coverage"),
            "state_note": window["state_note"],
        }
        shadow_by_window[name] = {
            key: value
            for key, value in shadow.items()
            if key != "rows"
        }
        shadow_by_window[name]["sample_rows"] = {
            "selected_signals": shadow["rows"]["selected_signals"][:20],
            "scarce_slot_deferred": shadow["rows"]["scarce_slot_deferred"][:20],
            "filing_event_candidates": shadow["rows"]["filing_event_candidates"][:20],
        }

    all_complete = all(
        (row["backtester_non_ohlcv_coverage"] or {}).get("complete_fraction") == 1.0
        for row in coverage_by_window.values()
    )
    field_availability = _field_availability_summary(sec_features_all)
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
    pit_caveats = [
        "SEC accepted_datetime/usable_trade_date is PIT-safe as EDGAR-public proxy, but not proof the production process observed the filing intraday.",
        "Historical earnings snapshots are repo/vendor snapshots and PIT-ish; EPS/revenue surprise remains null unless a trusted PIT consensus source exists.",
        "Directional filing-shock labels require same-row financial shock fields; form/item metadata alone is treated as unclear.",
        "First 20 trading days of the old_thin window are left-censored for recent-filing lookback because older non-OHLCV artifacts were not requested.",
    ]
    decision = "shadow_only" if all_complete else "data_gap"
    next_action = (
        "Use the complete replay dataset to build a default-off candidate-row tagging harness that persists all generated candidates, not only selected trades and scarce-slot deferrals."
        if all_complete
        else "Repair missing_by_artifact before any filing-shock shadow alpha."
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now_iso(),
        "lane": "alpha_discovery",
        "change_type": "measurement_repair_plus_shadow_tagging",
        "alpha_hypothesis_category": "entry_confirmation_overlay",
        "hypothesis": ticket["hypothesis"],
        "non_ohlcv_data_source": "SEC submissions/text/features, existing earnings snapshots, event snapshots, Form 4 transactions",
        "mechanism_family": "earnings_sec_filing_shock_event_confirmation_overlay",
        "single_causal_variable": ticket["single_causal_variable"],
        "date_range": {
            name: f"{window['start']} -> {window['end']}"
            for name, window in WINDOWS.items()
        },
        "market_regime_summary": {
            name: window["state_note"] for name, window in WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260418-004": "P-ERN data gap: earnings_event_long had 33.3% win rate and dragged EV while eps_estimate/surprise history were missing.",
            "exp-20260506-001": "Fresh SEC/earnings audit was data_gap: PIT filing rows existed but same-accession financial shock fields and closed outcomes were missing.",
            "playbook": "SEC/earnings filing shock remains high-priority only as auditable event confirmation or C grading; raw SEC threshold/source sweeps are repeat-guarded.",
        },
        "coverage_summary": {
            "all_windows_complete": all_complete,
            "by_window": coverage_by_window,
            "field_availability": field_availability,
        },
        "baseline_metrics": baseline_metrics,
        "shadow_summary": {
            "tag_definitions": {
                "A_no_recent_filing_event": "No PIT-safe SEC filing within 20 trading days before/on candidate date.",
                "B_positive_filing_shock": "Recent PIT-safe filing with positive same-row directional financial evidence and no negative directional field.",
                "C_negative_filing_shock": "Recent PIT-safe filing with negative same-row directional financial evidence and no positive directional field.",
                "D_unclear_or_missing_data": "Recent filing exists but directional fields are missing or mixed.",
            },
            "by_window": shadow_by_window,
        },
        "expected_value_score_delta": 0.0,
        "delta_metrics": {
            "strategy_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "reason": "Read-only coverage proof and shadow tagging; no production or replay policy changed.",
        },
        "production_impact": production_impact,
        "pit_caveats": pit_caveats,
        "decision": decision,
        "next_action": next_action,
        "status": "observed_only",
        "related_files": [
            "quant/experiments/exp_20260507_002_non_ohlcv_replay_coverage_filing_shock_shadow.py",
            "data/experiments/exp-20260507-002/non_ohlcv_replay_coverage_filing_shock_shadow.json",
            "docs/non_ohlcv_data_audit/sec_earnings_filing_shock_replay_coverage_exp-20260507-002_20260507.md",
            "experiments/tickets/exp-20260507-002.json",
            "experiments/logs/exp-20260507-002.json",
            "docs/experiment_log.jsonl",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_audit_markdown(payload)
    result_summary = {
        "decision": decision,
        "coverage_all_windows_complete": all_complete,
        "expected_value_score_delta": 0.0,
        "production_impact": production_impact,
    }
    updated_ticket = _update_ticket(ticket, result_summary)
    _update_registry(updated_ticket)
    _append_or_replace_jsonl(EXPERIMENT_LOG, {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": decision,
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "hypothesis": payload["hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "non_ohlcv_data_source": payload["non_ohlcv_data_source"],
        "date_range": payload["date_range"],
        "coverage_summary": {
            "all_windows_complete": all_complete,
            "complete_fraction_by_window": {
                name: (row["backtester_non_ohlcv_coverage"] or {}).get("complete_fraction")
                for name, row in coverage_by_window.items()
            },
            "missing_by_artifact_by_window": {
                name: (row["backtester_non_ohlcv_coverage"] or {}).get("missing_by_artifact")
                for name, row in coverage_by_window.items()
            },
            "field_availability": field_availability,
        },
        "baseline_metrics": baseline_metrics,
        "shadow_metrics_reference": {
            name: {
                "selected_signal_count": row["selected_signal_count"],
                "selected_signals_with_recent_filing": row["candidate_overlap"]["selected_signals_with_recent_filing"],
                "event_candidate_count": row["event_candidate_count"],
                "scarce_slot_deferred_count": row["scarce_slot_deferred_count"],
                "slot_conflict_comparable_count": row["scarce_slot_opportunity_cost"]["same_day_comparable_count"],
            }
            for name, row in shadow_by_window.items()
        },
        "expected_value_score_delta": 0.0,
        "production_impact": production_impact,
        "pit_caveats": pit_caveats,
        "next_action": next_action,
        "related_files": payload["related_files"],
    })
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "all_windows_complete": all_complete,
        "field_availability": field_availability,
        "outputs": payload["related_files"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
