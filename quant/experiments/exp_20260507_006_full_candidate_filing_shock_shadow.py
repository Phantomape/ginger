"""exp-20260507-006 full entry-candidate filing-shock shadow audit.

Default-off measurement experiment:
- asks backtester.py to persist full post-gate entry candidate decision rows;
- verifies persisted row counts match entry_execution_attribution;
- tags those rows with PIT-safe SEC filing recency;
- measures forward returns, overlap, and slot-conflict value.

No signal generation, ranking, sizing, exit, order, risk, or production adapter
logic is changed.
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


EXPERIMENT_ID = "exp-20260507-006"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "full_candidate_filing_shock_shadow.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
AUDIT_MD = (
    REPO_ROOT
    / "docs"
    / "non_ohlcv_data_audit"
    / "sec_earnings_filing_shock_full_candidate_exp-20260507-006_20260507.md"
)

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

HORIZONS = (5, 10, 20, 60)
RECENT_FILING_LOOKBACK_TRADING_DAYS = 20
ROUND_TRIP_COST = 0.0035
SLOT_CONFLICT_DECISIONS = {"slot_sliced", "scarce_slot_breakout_deferred"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, str) and value.strip():
        try:
            value = float(value)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
    return None


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(path)
    raw = payload.get("ohlcv") or payload
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in raw.items():
        converted = []
        for row in rows or []:
            date_value = str(row.get("Date") or row.get("date") or "")[:10]
            close = _as_float(row.get("Close") if "Close" in row else row.get("close"))
            if date_value and close is not None:
                converted.append({"date": date_value, "close": close})
        if converted:
            out[str(ticker).upper()] = sorted(converted, key=lambda item: item["date"])
    return out


def _idx_on_or_after(rows: list[dict[str, Any]], date_value: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= date_value:
            return idx
    return None


def _market_trading_day_distance(snapshot: dict[str, list[dict[str, Any]]], earlier: str, later: str) -> int | None:
    rows = snapshot.get("SPY") or next(iter(snapshot.values()), [])
    left = _idx_on_or_after(rows, earlier)
    right = _idx_on_or_after(rows, later)
    if left is None or right is None:
        return None
    return right - left


def _forward_returns(snapshot: dict[str, list[dict[str, Any]]], ticker: str, date_value: str) -> dict[str, Any]:
    rows = snapshot.get(ticker.upper()) or []
    start_idx = _idx_on_or_after(rows, date_value)
    if start_idx is None:
        return {f"ret_{horizon}d": None for horizon in HORIZONS} | {"base_date": None, "base_close": None}
    base = _as_float(rows[start_idx]["close"])
    out = {"base_date": rows[start_idx]["date"], "base_close": base}
    for horizon in HORIZONS:
        horizon_idx = start_idx + horizon
        if base is None or base <= 0 or horizon_idx >= len(rows):
            out[f"ret_{horizon}d"] = None
            out[f"end_date_{horizon}d"] = None
            continue
        end_close = _as_float(rows[horizon_idx]["close"])
        out[f"ret_{horizon}d"] = (
            (end_close / base) - 1.0 - ROUND_TRIP_COST
            if end_close is not None
            else None
        )
        out[f"end_date_{horizon}d"] = rows[horizon_idx]["date"]
    return out


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
            row["ticker"] = str(row.get("ticker") or "").upper()
            if not row.get("accepted_datetime") or not row.get("usable_trade_date"):
                row["pit_safe"] = False
            if row["ticker"]:
                rows.append(row)
    return rows


def _directional_field_counts(row: dict[str, Any]) -> tuple[list[str], list[str]]:
    positive: list[str] = []
    negative: list[str] = []
    for field in ["eps_surprise", "revenue_surprise", "gross_margin_delta", "fcf_to_net_income_gap"]:
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
    return positive, negative


def _classify_filing_shock(event: dict[str, Any] | None) -> dict[str, Any]:
    if not event:
        return {
            "filing_shock_tag": "A_no_recent_filing_event",
            "positive_evidence_fields": [],
            "negative_evidence_fields": [],
            "classification_reason": "no PIT-safe SEC filing within lookback",
        }
    positive, negative = _directional_field_counts(event)
    if positive and not negative:
        tag = "B_positive_filing_shock"
        reason = "positive same-row financial shock field"
    elif negative and not positive:
        tag = "C_negative_filing_shock"
        reason = "negative same-row financial shock field"
    else:
        tag = "D_unclear_or_missing_data"
        reason = "recent filing exists but directional financial shock fields are missing or mixed"
    return {
        "filing_shock_tag": tag,
        "positive_evidence_fields": positive,
        "negative_evidence_fields": negative,
        "classification_reason": reason,
    }


def _latest_recent_event(
    events_by_ticker: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, list[dict[str, Any]]],
    ticker: str,
    date_value: str,
) -> tuple[dict[str, Any] | None, int | None]:
    best = None
    best_distance = None
    for row in events_by_ticker.get(ticker.upper(), []):
        usable = str(row.get("usable_trade_date") or "")[:10]
        if not usable or usable > date_value or not row.get("pit_safe", False):
            continue
        distance = _market_trading_day_distance(snapshot, usable, date_value)
        if distance is None or distance < 0 or distance > RECENT_FILING_LOOKBACK_TRADING_DAYS:
            continue
        if best is None or distance < (best_distance or 10**9):
            best = row
            best_distance = distance
    return best, best_distance


def _event_reference(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    return {
        "form_type": event.get("form_type"),
        "accepted_datetime": event.get("accepted_datetime"),
        "usable_trade_date": event.get("usable_trade_date"),
        "source_accession": event.get("source_accession"),
        "eight_k_item_type": event.get("eight_k_item_type"),
        "pit_safe": event.get("pit_safe"),
        "field_availability": event.get("field_availability"),
        "gap_reasons": event.get("gap_reasons"),
    }


def _summarize_values(values: list[Any]) -> dict[str, Any]:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if not clean:
        return {"count": 0, "avg_pct": None, "median_pct": None, "win_rate": None, "best_pct": None, "worst_pct": None}
    return {
        "count": len(clean),
        "avg_pct": round(mean(clean) * 100.0, 4),
        "median_pct": round(median(clean) * 100.0, 4),
        "win_rate": round(sum(1 for value in clean if value > 0) / len(clean), 4),
        "best_pct": round(max(clean) * 100.0, 4),
        "worst_pct": round(min(clean) * 100.0, 4),
    }


def _summarize_forward_by_tag(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
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
                f"{horizon}d": _summarize_values([row.get(f"ret_{horizon}d") for row in subset])
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
        "vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
    }


def _field_availability_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    availability = Counter()
    gaps = Counter()
    directional = 0
    for row in rows:
        for field, status in (row.get("field_availability") or {}).items():
            availability[f"{field}:{status}"] += 1
        for reason in row.get("gap_reasons") or []:
            gaps[str(reason)] += 1
        positive, negative = _directional_field_counts(row)
        if positive or negative:
            directional += 1
    return {
        "sec_feature_rows": len(rows),
        "pit_safe_rows": sum(1 for row in rows if row.get("pit_safe", False)),
        "pit_safe_fraction": _safe_ratio(sum(1 for row in rows if row.get("pit_safe", False)), len(rows)),
        "directional_financial_shock_rows": directional,
        "field_availability_top": dict(availability.most_common(20)),
        "gap_reasons_top": dict(gaps.most_common(20)),
    }


def _validate_candidate_artifact(payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("candidate_events") or []
    reason_counts = Counter(event.get("decision") or "unknown" for event in events)
    expected = result.get("entry_execution_attribution") or {}
    return {
        "candidate_events_match": len(events) == expected.get("candidate_events"),
        "reason_counts_match": dict(sorted(reason_counts.items())) == (expected.get("reason_counts") or {}),
        "persisted_candidate_events": len(events),
        "attribution_candidate_events": expected.get("candidate_events"),
        "persisted_reason_counts": dict(sorted(reason_counts.items())),
        "attribution_reason_counts": expected.get("reason_counts"),
    }


def _tag_candidate_events(
    window_name: str,
    window: dict[str, str],
    snapshot: dict[str, list[dict[str, Any]]],
    candidate_events: list[dict[str, Any]],
    sec_features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events_by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sec_features:
        ticker = row.get("ticker")
        usable = str(row.get("usable_trade_date") or "")[:10]
        if ticker and usable <= window["end"]:
            events_by_ticker[ticker].append(row)
    for ticker in events_by_ticker:
        events_by_ticker[ticker].sort(
            key=lambda item: (str(item.get("usable_trade_date") or ""), str(item.get("accepted_datetime") or "")),
            reverse=True,
        )

    tagged = []
    for row in candidate_events:
        ticker = str(row.get("ticker") or "").upper()
        date_value = str(row.get("date") or "")[:10]
        event, distance = _latest_recent_event(events_by_ticker, snapshot, ticker, date_value)
        classification = _classify_filing_shock(event)
        tagged.append({
            "window": window_name,
            "ticker": ticker,
            "strategy": row.get("strategy"),
            "candidate_date": date_value,
            "decision": row.get("decision"),
            "candidate_rank": row.get("candidate_rank"),
            "available_slots_at_entry_loop": row.get("available_slots_at_entry_loop"),
            "signal_snapshot": row.get("signal_snapshot"),
            "recent_filing_distance_trading_days": distance,
            "recent_filing": _event_reference(event),
            **classification,
            **_forward_returns(snapshot, ticker, date_value),
        })
    return tagged


def _window_shadow_summary(tagged: list[dict[str, Any]]) -> dict[str, Any]:
    entered = [row for row in tagged if row.get("decision") == "entered"]
    skipped = [row for row in tagged if row.get("decision") != "entered"]
    slot_candidates = [row for row in tagged if row.get("decision") in SLOT_CONFLICT_DECISIONS]
    entered_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entered:
        entered_by_date[row["candidate_date"]].append(row)

    slot_deltas = []
    slot_examples = []
    for row in slot_candidates:
        entered_returns = [
            item.get("ret_20d")
            for item in entered_by_date.get(row["candidate_date"], [])
            if isinstance(item.get("ret_20d"), (int, float))
        ]
        own_ret = row.get("ret_20d")
        if not entered_returns or not isinstance(own_ret, (int, float)):
            continue
        delta = float(own_ret) - mean(entered_returns)
        slot_deltas.append(delta)
        slot_examples.append({
            "date": row["candidate_date"],
            "ticker": row["ticker"],
            "decision": row["decision"],
            "tag": row["filing_shock_tag"],
            "candidate_20d_return": round(float(own_ret), 6),
            "same_day_entered_avg_20d_return": round(mean(entered_returns), 6),
            "slot_conflict_delta_20d": round(delta, 6),
        })

    decision_counts = Counter(row.get("decision") or "unknown" for row in tagged)
    tag_counts = Counter(row.get("filing_shock_tag") for row in tagged)
    recent = [row for row in tagged if row.get("filing_shock_tag") != "A_no_recent_filing_event"]
    return {
        "candidate_count": len(tagged),
        "entered_count": len(entered),
        "skipped_count": len(skipped),
        "decision_counts": dict(sorted(decision_counts.items())),
        "tag_counts": dict(sorted(tag_counts.items())),
        "candidate_overlap": {
            "entered_overlap_count": len(entered),
            "entered_overlap_rate": _safe_ratio(len(entered), len(tagged)),
            "candidates_with_recent_filing": len(recent),
            "recent_filing_overlap_rate": _safe_ratio(len(recent), len(tagged)),
            "entered_with_recent_filing": sum(1 for row in entered if row.get("filing_shock_tag") != "A_no_recent_filing_event"),
            "slot_candidates_with_recent_filing": sum(1 for row in slot_candidates if row.get("filing_shock_tag") != "A_no_recent_filing_event"),
        },
        "forward_returns_by_tag": _summarize_forward_by_tag(tagged),
        "entered_forward_returns_by_tag": _summarize_forward_by_tag(entered),
        "slot_conflict_value": {
            "slot_candidate_count": len(slot_candidates),
            "same_day_comparable_count": len(slot_deltas),
            "distribution_vs_same_day_entered_avg_20d": _summarize_values(slot_deltas),
            "examples": slot_examples[:30],
        },
        "sample_tagged_rows": tagged[:30],
    }


def _append_or_replace_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if existing.get("experiment_id") != record.get("experiment_id"):
                lines.append(json.dumps(existing, ensure_ascii=False))
    lines.append(json.dumps(record, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_ticket(ticket: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    ticket["status"] = "observed_only"
    ticket["completed_at"] = _utc_now_iso()
    ticket["result"] = result
    _write_json(TICKET_JSON, ticket)
    return ticket


def _update_registry(ticket: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON)
    entry = {
        "experiment_id": EXPERIMENT_ID,
        "status": ticket["status"],
        "lane": ticket.get("lane"),
        "owner": ticket.get("owner"),
        "hypothesis": ticket.get("hypothesis"),
        "ticket_file": f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
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


def _write_audit_md(payload: dict[str, Any]) -> None:
    lines = [
        f"# Full Candidate Filing-Shock Shadow Audit ({EXPERIMENT_ID})",
        "",
        "## Decision",
        payload["decision"],
        "",
        "## Coverage",
        "| window | complete_fraction | candidate rows | entered | recent filing rows | slot comparables |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["shadow_summary"]["by_window"].items():
        coverage = payload["coverage_summary"]["by_window"][name]
        overlap = row["candidate_overlap"]
        slot = row["slot_conflict_value"]
        lines.append(
            f"| {name} | {coverage['complete_fraction']} | {row['candidate_count']} | "
            f"{row['entered_count']} | {overlap['candidates_with_recent_filing']} | "
            f"{slot['same_day_comparable_count']} |"
        )
    lines.extend([
        "",
        "## Field Availability",
        json.dumps(payload["field_availability"], indent=2, ensure_ascii=False),
        "",
        "## Production Impact",
        json.dumps(payload["production_impact"], indent=2, ensure_ascii=False),
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
    baseline_metrics = {}
    coverage_summary = {"by_window": {}}
    shadow_by_window = {}
    validation_by_window = {}
    all_sec_features = []

    for name, window in WINDOWS.items():
        candidate_path = OUT_DIR / f"entry_candidate_events_{name}.json"
        engine = BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
            require_non_ohlcv=True,
            save_entry_candidate_events_path=str(candidate_path),
        )
        result = engine.run()
        if "error" in result:
            raise RuntimeError(f"{name} require-non-OHLCV failed: {result['error']}")

        candidate_payload = _load_json(candidate_path)
        validation = _validate_candidate_artifact(candidate_payload, result)
        if not validation["candidate_events_match"] or not validation["reason_counts_match"]:
            raise RuntimeError(f"{name} persisted candidate event validation failed: {validation}")

        snapshot = _load_snapshot(REPO_ROOT / window["snapshot"])
        sec_features = _load_sec_features(window["start"], window["end"])
        all_sec_features.extend(sec_features)
        tagged = _tag_candidate_events(
            name,
            window,
            snapshot,
            candidate_payload.get("candidate_events") or [],
            sec_features,
        )
        _write_json(OUT_DIR / f"tagged_entry_candidates_{name}.json", {"rows": tagged})

        coverage = result.get("non_ohlcv_coverage") or {}
        coverage_summary["by_window"][name] = {
            "start": window["start"],
            "end": window["end"],
            "complete_fraction": coverage.get("complete_fraction"),
            "complete_days": coverage.get("complete_days"),
            "business_days": coverage.get("business_days"),
            "missing_by_artifact": coverage.get("missing_by_artifact"),
            "biased_days": coverage.get("biased_days"),
            "candidate_artifact": str(candidate_path.relative_to(REPO_ROOT)),
        }
        baseline_metrics[name] = _metric_snapshot(result)
        shadow_by_window[name] = _window_shadow_summary(tagged)
        validation_by_window[name] = validation

    all_complete = all(
        row.get("complete_fraction") == 1.0
        for row in coverage_summary["by_window"].values()
    )
    field_availability = _field_availability_summary(all_sec_features)
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": True,
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
        "Fill directional same-accession/companyfacts or PIT consensus fields; "
        "full candidate persistence is now available for default-off replay."
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now_iso(),
        "status": "observed_only",
        "decision": decision,
        "lane": "alpha_discovery",
        "change_type": "measurement_repair_plus_full_candidate_shadow_tagging",
        "hypothesis": ticket["hypothesis"],
        "mechanism_family": "earnings_sec_filing_shock_event_confirmation_overlay",
        "single_causal_variable": ticket["single_causal_variable"],
        "non_ohlcv_data_source": "SEC submissions/text/features plus existing earnings snapshots",
        "date_range": {name: f"{w['start']} -> {w['end']}" for name, w in WINDOWS.items()},
        "market_regime_summary": {name: w["state_note"] for name, w in WINDOWS.items()},
        "historical_experiment_check": {
            "exp-20260507-002": "Coverage complete but slot value was limited to selected trades plus scarce-slot deferrals; full candidate rows were not persisted.",
            "exp-20260507-004": "Experiment-local candidate tagging already covered 138 post-filter rows; this run turns the same row surface into a default-off backtester artifact and validates counts against entry_execution_attribution.",
            "exp-20260506-001": "Fresh SEC audit found PIT rows but no direction-grade financial shock fields.",
            "exp-20260418-004": "P-ERN remains blocked by missing earnings surprise history / estimates.",
        },
        "coverage_summary": {
            "all_windows_complete": all_complete,
            **coverage_summary,
        },
        "field_availability": field_availability,
        "baseline_metrics": baseline_metrics,
        "shadow_summary": {
            "tag_definitions": {
                "A_no_recent_filing_event": "No PIT-safe SEC filing within 20 trading days before/on candidate date.",
                "B_positive_filing_shock": "Recent PIT-safe filing with positive same-row directional financial evidence and no negative field.",
                "C_negative_filing_shock": "Recent PIT-safe filing with negative same-row directional financial evidence and no positive field.",
                "D_unclear_or_missing_data": "Recent filing exists but directional fields are missing or mixed.",
            },
            "candidate_artifact_validation": validation_by_window,
            "by_window": shadow_by_window,
        },
        "expected_value_score_delta": 0.0,
        "delta_metrics": {
            "strategy_metrics_changed": False,
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "reason": "Default-off instrumentation and shadow tagging only.",
        },
        "production_impact": production_impact,
        "pit_caveats": [
            "SEC accepted_datetime/usable_trade_date is PIT-safe as EDGAR-public proxy, but not proof production observed it intraday.",
            "EPS/revenue surprise and same-accession financial shock fields remain null without trusted PIT consensus/same-accession facts.",
            "Full candidate rows are post-gate entry candidates, not raw universe-wide generated signals before all filters.",
        ],
        "next_action": next_action,
        "related_files": [
            "quant/backtester.py",
            "quant/experiments/exp_20260507_006_full_candidate_filing_shock_shadow.py",
            "data/experiments/exp-20260507-006/full_candidate_filing_shock_shadow.json",
            "docs/non_ohlcv_data_audit/sec_earnings_filing_shock_full_candidate_exp-20260507-006_20260507.md",
            "docs/experiments/tickets/exp-20260507-006.json",
            "docs/experiments/logs/exp-20260507-006.json",
            "docs/experiment_log.jsonl",
        ],
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_audit_md(payload)
    updated_ticket = _update_ticket(ticket, {
        "decision": decision,
        "candidate_artifact_validation_passed": all(
            row["candidate_events_match"] and row["reason_counts_match"]
            for row in validation_by_window.values()
        ),
        "coverage_all_windows_complete": all_complete,
        "expected_value_score_delta": 0.0,
        "production_impact": production_impact,
    })
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
                name: row["complete_fraction"]
                for name, row in coverage_summary["by_window"].items()
            },
        },
        "field_availability": field_availability,
        "baseline_metrics": baseline_metrics,
        "shadow_metrics_reference": {
            name: {
                "candidate_count": row["candidate_count"],
                "entered_count": row["entered_count"],
                "candidates_with_recent_filing": row["candidate_overlap"]["candidates_with_recent_filing"],
                "slot_candidate_count": row["slot_conflict_value"]["slot_candidate_count"],
                "slot_conflict_comparable_count": row["slot_conflict_value"]["same_day_comparable_count"],
            }
            for name, row in shadow_by_window.items()
        },
        "expected_value_score_delta": 0.0,
        "production_impact": production_impact,
        "pit_caveats": payload["pit_caveats"],
        "next_action": next_action,
        "related_files": payload["related_files"],
    })
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": decision,
        "all_windows_complete": all_complete,
        "field_availability": field_availability,
        "candidate_counts": {
            name: {
                "candidate_count": row["candidate_count"],
                "entered_count": row["entered_count"],
                "candidates_with_recent_filing": row["candidate_overlap"]["candidates_with_recent_filing"],
                "slot_conflict_comparable_count": row["slot_conflict_value"]["same_day_comparable_count"],
            }
            for name, row in shadow_by_window.items()
        },
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
