"""Observe-only governance helpers for the space catalyst theme.

The space catalyst sleeve starts as a shadow universe, not a pilot trade
adapter. It lets the daily system and experiments see a clean, auditable pool
without letting UFO/SpaceX headlines bypass the normal core and pilot gates.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from pilot_sleeve import (
    SPACE_CATALYST_SHADOW_SLEEVE_NAME,
    SPACE_CATALYST_THEME_SEGMENTS,
)
from universe_manager import (
    DEFAULT_EVENTS_PATH,
    DEFAULT_REGISTRY_PATH,
    records_as_of,
)


SPACE_CATALYST_LLM_EVENT_FIELDS = (
    "uap_attention_spike",
    "spacex_ipo_proxy",
    "government_space_contract",
    "launch_success",
    "launch_failure",
    "dilution_risk",
    "meme_spike",
)

SPACE_CATALYST_PROMOTION_GATES = {
    "mode": "observe_only",
    "minimum_active_signal_days": 30,
    "minimum_closed_decisions": 10,
    "direct_pnl_required": "> 0",
    "replacement_value_required": "> 0",
    "risk_adjusted_replacement_value_required": "> 0",
    "max_single_ticker_positive_contribution": 0.70,
}

SPACE_CATALYST_DATA_VENDOR_BREAKOUT_TICKERS = ("PL", "BKSY")
SPACE_CATALYST_DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.1
SPACE_CATALYST_LAUNCH_CONNECTIVITY_TREND_TICKERS = ("RKLB", "ASTS")
SPACE_CATALYST_LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
SPACE_CATALYST_OFFICIAL_TREND_TARGET_ATR_MULT = 5.0

SPACE_CATALYST_FORWARD_HYPOTHESIS = {
    "experiment_id": "exp-20260511-032",
    "mode": "default_off_forward_observation",
    "candidate_pool": "official_catalyst_operating_growth",
    "risk_budget_scalar": 0.75,
    "data_vendor_breakout_risk_scalar": (
        SPACE_CATALYST_DATA_VENDOR_BREAKOUT_RISK_SCALAR
    ),
    "data_vendor_breakout_tickers": list(SPACE_CATALYST_DATA_VENDOR_BREAKOUT_TICKERS),
    "launch_connectivity_trend_risk_scalar": (
        SPACE_CATALYST_LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
    ),
    "launch_connectivity_trend_tickers": list(
        SPACE_CATALYST_LAUNCH_CONNECTIVITY_TREND_TICKERS
    ),
    "official_trend_target_atr_mult": (
        SPACE_CATALYST_OFFICIAL_TREND_TARGET_ATR_MULT
    ),
    "live_slots": 0,
    "included_tickers": ["RKLB", "ASTS", "LUNR", "PL", "RDW", "BKSY"],
    "excluded_buckets": [
        "attention_only",
        "theme_beta_benchmark",
        "quarantine_meme",
        "mature_satcom_breadth",
    ],
    "requires_forward_replacement_value": True,
}

SPACE_CATALYST_STOP_RULES = (
    "Do not trade from UAP/disclosure headlines alone.",
    "Do not trade until a separate pilot promotion creates explicit live slots.",
    "Treat offerings, dilution, launch failure, and mission binary risk as veto fields.",
)

SPACE_CATALYST_EVENT_LEDGER_SCHEMA_VERSION = 1
SPACE_CATALYST_EVENT_LEDGER_NAME = "SPACE_CATALYST_EVENT_STATE_SHADOW_LEDGER"
SPACE_CATALYST_EVENT_LEDGER_RULE_VERSION = "space_catalyst_event_state_v1"
SPACE_CATALYST_EVENT_INITIAL_NOTIONAL = 10_000.0
SPACE_CATALYST_EVENT_HORIZONS = (1, 5, 10, 20)
SPACE_CATALYST_EVENT_BENCHMARKS = ("SPY", "QQQ", "ARKX", "UFO")
SPACE_CATALYST_NON_OPERATING_SEGMENTS = (
    "quarantine_meme",
    "theme_beta_benchmark",
)
DEFAULT_SPACE_CATALYST_EVENT_SEED_PATH = Path("data/space_catalyst_event_seeds.jsonl")
DEFAULT_SPACE_CATALYST_EVENT_LEDGER_PATH = Path(
    "data/space_catalyst_event_state_shadow_ledger.jsonl"
)
DEFAULT_SPACE_CATALYST_EVENT_SUMMARY_PATH = Path(
    "data/space_catalyst_event_state_shadow_summary.json"
)


def space_catalyst_forward_risk_scalar(ticker: str, strategy: str) -> float:
    """Return the extra default-off forward scalar for Space sleeve attribution."""
    ticker_upper = str(ticker or "").upper()
    strategy_key = str(strategy or "").lower()
    scalar = 1.0
    if (
        ticker_upper in SPACE_CATALYST_DATA_VENDOR_BREAKOUT_TICKERS
        and strategy_key == "breakout_long"
    ):
        scalar *= SPACE_CATALYST_DATA_VENDOR_BREAKOUT_RISK_SCALAR
    if (
        ticker_upper in SPACE_CATALYST_LAUNCH_CONNECTIVITY_TREND_TICKERS
        and strategy_key == "trend_long"
    ):
        scalar *= SPACE_CATALYST_LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
    return scalar


def space_catalyst_forward_target_atr_mult(
    ticker: str,
    strategy: str,
    current_target_atr_mult: float | None = None,
) -> float | None:
    """Return the default-off Space trend target width for forward attribution."""
    ticker_upper = str(ticker or "").upper()
    strategy_key = str(strategy or "").lower()
    if (
        ticker_upper in SPACE_CATALYST_FORWARD_HYPOTHESIS["included_tickers"]
        and strategy_key == "trend_long"
    ):
        return SPACE_CATALYST_OFFICIAL_TREND_TARGET_ATR_MULT
    return current_target_atr_mult


def empty_space_catalyst_shadow_snapshot(as_of, reason: str = "not_built") -> dict:
    return {
        "sleeve": SPACE_CATALYST_SHADOW_SLEEVE_NAME,
        "as_of": str(as_of),
        "mode": "observe_only",
        "candidate_count": 0,
        "status_counts": {},
        "segment_counts": {},
        "tickers_by_segment": {},
        "trade_enabled_tickers": [],
        "llm_event_fields": list(SPACE_CATALYST_LLM_EVENT_FIELDS),
        "promotion_gates": deepcopy(SPACE_CATALYST_PROMOTION_GATES),
        "forward_hypothesis": deepcopy(SPACE_CATALYST_FORWARD_HYPOTHESIS),
        "stop_rules": list(SPACE_CATALYST_STOP_RULES),
        "reason": reason,
    }


def empty_space_catalyst_event_ledger(as_of, reason: str = "not_built") -> dict:
    return {
        "schema_version": SPACE_CATALYST_EVENT_LEDGER_SCHEMA_VERSION,
        "ledger_name": SPACE_CATALYST_EVENT_LEDGER_NAME,
        "rule_version": SPACE_CATALYST_EVENT_LEDGER_RULE_VERSION,
        "asof_date": str(as_of)[:10],
        "generated_at": _utc_now_iso(),
        "enabled": False,
        "trade_enabled": False,
        "mode": "observe_only",
        "seed_event_count": 0,
        "active_event_count": 0,
        "event_row_count": 0,
        "closed_decision_count": 0,
        "pending_decision_count": 0,
        "event_rows": [],
        "aggregate": _empty_event_aggregate(),
        "promotion_gate": {
            "passed": False,
            "reason": reason,
            "minimum_closed_decisions": SPACE_CATALYST_PROMOTION_GATES[
                "minimum_closed_decisions"
            ],
        },
        "data_source": {"status": reason},
        "production_impact": _event_ledger_production_impact(),
    }


def load_space_catalyst_event_seeds(
    source_path: Path | str = DEFAULT_SPACE_CATALYST_EVENT_SEED_PATH,
) -> list[dict[str, Any]]:
    """Load manually reviewed Space event seeds for observe-only attribution."""
    path = Path(source_path)
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            row = _normalise_event_seed(payload)
            if row:
                rows.append(row)
    return sorted(rows, key=lambda row: (row["event_date"], row["event_id"]))


def space_catalyst_event_tickers(
    as_of,
    *,
    events: list[dict[str, Any]] | None = None,
    source_path: Path | str = DEFAULT_SPACE_CATALYST_EVENT_SEED_PATH,
    space_catalyst_shadow: dict[str, Any] | None = None,
) -> list[str]:
    """Return tickers needed to evaluate the current Space event ledger."""
    asof_date = str(as_of)[:10]
    seeds = events if events is not None else load_space_catalyst_event_seeds(source_path)
    tickers = set(SPACE_CATALYST_EVENT_BENCHMARKS)
    for event in seeds:
        if str(event.get("event_date") or "")[:10] <= asof_date:
            tickers.update(str(ticker).upper() for ticker in event.get("tickers") or [])
    tickers.update(_same_theme_tickers(space_catalyst_shadow))
    return sorted(ticker for ticker in tickers if ticker)


def build_space_catalyst_event_ledger_snapshot(
    *,
    as_of,
    events: list[dict[str, Any]] | None = None,
    source_path: Path | str = DEFAULT_SPACE_CATALYST_EVENT_SEED_PATH,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    space_catalyst_shadow: dict[str, Any] | None = None,
    core_signals: list[dict[str, Any]] | None = None,
    entry_execution_plan: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build an observe-only event-state snapshot for the Space catalyst sleeve."""
    asof_date = str(as_of)[:10]
    generated_at = generated_at or datetime.now(timezone.utc)
    seeds = events if events is not None else load_space_catalyst_event_seeds(source_path)
    seeds = [row for row in (_normalise_event_seed(row) for row in seeds) if row]
    active_events = [
        event for event in seeds if str(event.get("event_date") or "")[:10] <= asof_date
    ]
    rows_by_ticker = {
        str(ticker).upper(): _truncate_rows(_normalise_ohlcv_rows(rows), asof_date)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    same_theme_tickers = _same_theme_tickers(space_catalyst_shadow)
    if not same_theme_tickers:
        same_theme_tickers = sorted(
            {
                ticker
                for event in active_events
                for ticker in event.get("tickers") or []
                if ticker not in SPACE_CATALYST_EVENT_BENCHMARKS
            }
        )
    core_alternatives = _same_day_core_alternatives(
        core_signals or [],
        entry_execution_plan or {},
    )

    event_rows = []
    for event in active_events:
        for ticker in event.get("tickers") or []:
            event_rows.append(
                _evaluate_event_ticker(
                    event=event,
                    ticker=ticker,
                    asof_date=asof_date,
                    rows_by_ticker=rows_by_ticker,
                    same_theme_tickers=same_theme_tickers,
                    space_catalyst_shadow=space_catalyst_shadow or {},
                    same_day_core_alternatives=core_alternatives,
                )
            )

    aggregate = _aggregate_event_rows(event_rows)
    closed_decisions = aggregate["closed_decision_count"]
    pending_decisions = len(event_rows) - closed_decisions
    promotion_gate = _space_event_promotion_gate(aggregate)
    return {
        "schema_version": SPACE_CATALYST_EVENT_LEDGER_SCHEMA_VERSION,
        "ledger_name": SPACE_CATALYST_EVENT_LEDGER_NAME,
        "rule_version": SPACE_CATALYST_EVENT_LEDGER_RULE_VERSION,
        "asof_date": asof_date,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "enabled": False,
        "trade_enabled": False,
        "mode": "observe_only",
        "seed_event_count": len(seeds),
        "active_event_count": len(active_events),
        "event_row_count": len(event_rows),
        "closed_decision_count": closed_decisions,
        "pending_decision_count": pending_decisions,
        "same_theme_tickers": same_theme_tickers,
        "benchmarks": list(SPACE_CATALYST_EVENT_BENCHMARKS),
        "horizons": list(SPACE_CATALYST_EVENT_HORIZONS),
        "initial_notional": SPACE_CATALYST_EVENT_INITIAL_NOTIONAL,
        "event_rows": event_rows,
        "aggregate": aggregate,
        "promotion_gate": promotion_gate,
        "parameters": {
            "entry_rule": "next_trading_day_close_after_event_date",
            "primary_closed_decision_horizon": "10d",
            "minimum_closed_decisions": SPACE_CATALYST_PROMOTION_GATES[
                "minimum_closed_decisions"
            ],
            "attention_only_is_attribution_not_promotion_evidence": True,
            "live_slots": 0,
        },
        "data_source": {
            "status": "loaded" if seeds else "missing_or_empty_seed_file",
            "source_path": str(source_path),
            "ohlcv_tickers_loaded": sorted(rows_by_ticker),
        },
        "production_impact": _event_ledger_production_impact(),
    }


def persist_space_catalyst_event_ledger(
    snapshot: dict[str, Any],
    *,
    ledger_path: Path | str = DEFAULT_SPACE_CATALYST_EVENT_LEDGER_PATH,
    summary_path: Path | str = DEFAULT_SPACE_CATALYST_EVENT_SUMMARY_PATH,
) -> dict[str, Any]:
    """Append one observe-only row per event/ticker/as-of and write a summary."""
    ledger = Path(ledger_path)
    summary = Path(summary_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)

    seen = _event_ledger_keys(ledger)
    appended = 0
    with ledger.open("a", encoding="utf-8") as handle:
        for event_row in snapshot.get("event_rows") or []:
            key = _event_ledger_key(event_row)
            if key in seen:
                continue
            row = deepcopy(event_row)
            row["schema_version"] = SPACE_CATALYST_EVENT_LEDGER_SCHEMA_VERSION
            row["ledger_name"] = SPACE_CATALYST_EVENT_LEDGER_NAME
            row["rule_version"] = SPACE_CATALYST_EVENT_LEDGER_RULE_VERSION
            row["logged_at"] = _utc_now_iso()
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            seen.add(key)
            appended += 1

    history = _read_jsonl_rows(ledger)
    history_by_bucket = Counter(str(row.get("semantic_bucket") or "") for row in history)
    history_by_ticker = Counter(str(row.get("ticker") or "") for row in history)
    out = {
        "schema_version": SPACE_CATALYST_EVENT_LEDGER_SCHEMA_VERSION,
        "ledger_name": SPACE_CATALYST_EVENT_LEDGER_NAME,
        "rule_version": SPACE_CATALYST_EVENT_LEDGER_RULE_VERSION,
        "updated_at": _utc_now_iso(),
        "asof_date": snapshot.get("asof_date"),
        "active_event_count": snapshot.get("active_event_count", 0),
        "event_row_count": snapshot.get("event_row_count", 0),
        "closed_decision_count": snapshot.get("closed_decision_count", 0),
        "pending_decision_count": snapshot.get("pending_decision_count", 0),
        "appended_count": appended,
        "ledger_row_count": len(history),
        "ledger_path": str(ledger),
        "summary_path": str(summary),
        "history_by_bucket": dict(sorted(history_by_bucket.items())),
        "history_by_ticker": dict(sorted(history_by_ticker.items())),
        "promotion_gate": snapshot.get("promotion_gate") or {},
        "aggregate": snapshot.get("aggregate") or {},
        "production_impact": _event_ledger_production_impact(),
    }
    with summary.open("w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return {**snapshot, "persistence": out}


def is_space_catalyst_record(record: dict | None) -> bool:
    record = record or {}
    sleeve = record.get("pilot_sleeve") or record.get("sleeve")
    theme = str(record.get("theme") or "").lower()
    return (
        sleeve == SPACE_CATALYST_SHADOW_SLEEVE_NAME
        or theme in SPACE_CATALYST_THEME_SEGMENTS
        or theme.startswith("space_")
    )


def space_catalyst_records_as_of(
    as_of,
    *,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
    include_quarantine: bool = True,
) -> dict[str, dict]:
    """Return point-in-time space catalyst records, including research rows."""
    records = records_as_of(
        as_of,
        registry_path=registry_path,
        events_path=events_path,
        prefer_events=True,
    )
    out = {}
    for ticker, record in sorted(records.items()):
        if not is_space_catalyst_record(record):
            continue
        if record.get("status") == "quarantine" and not include_quarantine:
            continue
        enriched = deepcopy(record)
        enriched.setdefault("ticker", ticker)
        enriched["pilot_sleeve"] = SPACE_CATALYST_SHADOW_SLEEVE_NAME
        enriched.setdefault(
            "theme_segment",
            SPACE_CATALYST_THEME_SEGMENTS.get(
                str(enriched.get("theme") or "").lower(),
                str(enriched.get("theme") or "unknown"),
            ),
        )
        out[ticker] = enriched
    return out


def build_space_catalyst_shadow_snapshot(
    as_of,
    *,
    registry_path: Path | str = DEFAULT_REGISTRY_PATH,
    events_path: Path | str = DEFAULT_EVENTS_PATH,
) -> dict:
    """Build a deterministic observe-only snapshot for daily reporting/logs."""
    records = space_catalyst_records_as_of(
        as_of,
        registry_path=registry_path,
        events_path=events_path,
    )
    status_counts = Counter(record.get("status") for record in records.values())
    segment_counts = Counter(record.get("theme_segment") for record in records.values())
    tickers_by_segment = defaultdict(list)
    trade_enabled = []
    for ticker, record in records.items():
        tickers_by_segment[record.get("theme_segment")].append(ticker)
        if record.get("first_trade_allowed_as_of") and (
            float(record.get("max_capital_scalar") or 0.0) > 0
            or float(record.get("max_risk_scalar") or 0.0) > 0
        ):
            trade_enabled.append(ticker)

    return {
        "sleeve": SPACE_CATALYST_SHADOW_SLEEVE_NAME,
        "as_of": str(as_of),
        "mode": "observe_only",
        "candidate_count": len(records),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: str(item[0]))),
        "segment_counts": dict(sorted(segment_counts.items(), key=lambda item: str(item[0]))),
        "tickers_by_segment": {
            segment: sorted(tickers)
            for segment, tickers in sorted(
                tickers_by_segment.items(),
                key=lambda item: str(item[0]),
            )
        },
        "trade_enabled_tickers": sorted(trade_enabled),
        "llm_event_fields": list(SPACE_CATALYST_LLM_EVENT_FIELDS),
        "promotion_gates": deepcopy(SPACE_CATALYST_PROMOTION_GATES),
        "forward_hypothesis": deepcopy(SPACE_CATALYST_FORWARD_HYPOTHESIS),
        "stop_rules": list(SPACE_CATALYST_STOP_RULES),
    }


def _normalise_event_seed(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    event_date = str(
        payload.get("event_date")
        or payload.get("usable_trade_date")
        or payload.get("asof_date")
        or ""
    )[:10]
    if not event_date:
        return None
    raw_tickers = payload.get("tickers")
    if raw_tickers is None:
        raw_tickers = [payload.get("ticker")]
    elif isinstance(raw_tickers, str):
        raw_tickers = [raw_tickers]
    tickers = sorted({str(ticker).upper() for ticker in raw_tickers or [] if ticker})
    if not tickers:
        return None
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        event_id = f"space_event_{event_date}_{'_'.join(tickers)}".lower()
    fields = payload.get("event_fields") or []
    if isinstance(fields, str):
        fields = [fields]
    return {
        "event_id": event_id,
        "event_date": event_date,
        "tickers": tickers,
        "semantic_bucket": str(payload.get("semantic_bucket") or "unknown"),
        "event_fields": [str(field) for field in fields if field],
        "description": payload.get("description"),
        "source_url": payload.get("source_url"),
        "source_type": payload.get("source_type") or "manual_review_seed",
    }


def _evaluate_event_ticker(
    *,
    event: dict[str, Any],
    ticker: str,
    asof_date: str,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    same_theme_tickers: list[str],
    space_catalyst_shadow: dict[str, Any],
    same_day_core_alternatives: list[dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(ticker or "").upper()
    row = {
        "asof_date": asof_date,
        "event_id": event["event_id"],
        "event_date": event["event_date"],
        "ticker": ticker,
        "semantic_bucket": event["semantic_bucket"],
        "event_fields": list(event.get("event_fields") or []),
        "description": event.get("description"),
        "source_url": event.get("source_url"),
        "source_type": event.get("source_type"),
        "theme_segment": _theme_segment_for_ticker(space_catalyst_shadow, ticker),
        "initial_notional": SPACE_CATALYST_EVENT_INITIAL_NOTIONAL,
        "entry_date": None,
        "outcome_status": "pending",
        "pending_reason": None,
        "closed_decision": False,
        "same_day_core_alternative_count": len(same_day_core_alternatives),
        "same_day_core_alternatives": same_day_core_alternatives[:10],
        "horizons": {},
        "trade_enabled": False,
        "production_impact": _event_ledger_production_impact(),
    }
    rows = rows_by_ticker.get(ticker) or []
    if not rows:
        row["pending_reason"] = "missing_ohlcv"
        return row

    entry_date = _next_trading_date(rows, event["event_date"])
    row["entry_date"] = entry_date
    if not entry_date:
        row["pending_reason"] = "no_trading_date_after_event"
        return row

    mature_count = 0
    for horizon in SPACE_CATALYST_EVENT_HORIZONS:
        horizon_key = f"{horizon}d"
        exit_date = _horizon_date(rows, entry_date, horizon)
        if not exit_date:
            row["horizons"][horizon_key] = {
                "status": "pending",
                "pending_reason": "horizon_not_mature",
            }
            continue
        event_outcome = _ticker_return(rows_by_ticker, ticker, entry_date, exit_date)
        benchmarks = {
            benchmark: _ticker_return(rows_by_ticker, benchmark, entry_date, exit_date)
            for benchmark in SPACE_CATALYST_EVENT_BENCHMARKS
        }
        same_theme = _basket_return(
            rows_by_ticker,
            same_theme_tickers,
            entry_date,
            exit_date,
        )
        result = {
            "status": "mature",
            "exit_date": exit_date,
            "event_return": _round(event_outcome.get("return")),
            "cash_relative_pnl": _round(event_outcome.get("pnl_proxy"), 2),
            "same_theme_basket": same_theme,
            "benchmarks": benchmarks,
            "same_theme_replacement_value": None,
            "ufo_relative_value": None,
            "arkx_relative_value": None,
            "spy_relative_value": None,
            "qqq_relative_value": None,
            "core_replacement_value": None,
            "core_replacement_value_status": "pending_closed_core_outcome",
        }
        event_return = event_outcome.get("return")
        if event_return is not None:
            if same_theme.get("return") is not None:
                result["same_theme_replacement_value"] = _round(
                    (event_return - same_theme["return"])
                    * SPACE_CATALYST_EVENT_INITIAL_NOTIONAL,
                    2,
                )
            for benchmark in SPACE_CATALYST_EVENT_BENCHMARKS:
                benchmark_return = benchmarks[benchmark].get("return")
                if benchmark_return is not None:
                    result[f"{benchmark.lower()}_relative_value"] = _round(
                        (event_return - benchmark_return)
                        * SPACE_CATALYST_EVENT_INITIAL_NOTIONAL,
                        2,
                    )
            mature_count += 1
        row["horizons"][horizon_key] = result

    if mature_count:
        row["outcome_status"] = (
            "mature"
            if mature_count == len(SPACE_CATALYST_EVENT_HORIZONS)
            else "partially_mature"
        )
    else:
        row["pending_reason"] = "no_mature_horizons"
    row["closed_decision"] = (
        (row.get("horizons") or {}).get("10d", {}).get("status") == "mature"
        and (row.get("horizons") or {}).get("10d", {}).get("event_return") is not None
    )
    return row


def _aggregate_event_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _empty_event_aggregate()
    by_bucket: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    overall: dict[str, list[float]] = defaultdict(list)
    closed_rows = []
    official_closed_rows = []
    for row in rows:
        bucket = str(row.get("semantic_bucket") or "unknown")
        if row.get("closed_decision"):
            closed_rows.append(row)
            if bucket != "attention_only":
                official_closed_rows.append(row)
        for horizon_key, horizon in (row.get("horizons") or {}).items():
            if horizon.get("status") != "mature":
                continue
            metrics = {
                f"{horizon_key}_return": horizon.get("event_return"),
                f"{horizon_key}_cash_pnl": horizon.get("cash_relative_pnl"),
                f"{horizon_key}_same_theme_value": horizon.get(
                    "same_theme_replacement_value"
                ),
                f"{horizon_key}_ufo_relative_value": horizon.get("ufo_relative_value"),
                f"{horizon_key}_arkx_relative_value": horizon.get("arkx_relative_value"),
                f"{horizon_key}_spy_relative_value": horizon.get("spy_relative_value"),
                f"{horizon_key}_qqq_relative_value": horizon.get("qqq_relative_value"),
            }
            for key, value in metrics.items():
                numeric = _as_float(value)
                if numeric is None:
                    continue
                overall[key].append(numeric)
                by_bucket[bucket][key].append(numeric)
    return {
        "event_row_count": len(rows),
        "closed_decision_count": len(closed_rows),
        "official_closed_decision_count": len(official_closed_rows),
        "attention_only_closed_decision_count": len(closed_rows)
        - len(official_closed_rows),
        "pending_decision_count": len(rows) - len(closed_rows),
        "by_semantic_bucket_count": dict(
            sorted(Counter(str(row.get("semantic_bucket") or "unknown") for row in rows).items())
        ),
        "overall": {
            key: _summarize(values)
            for key, values in sorted(overall.items())
        },
        "by_semantic_bucket": {
            bucket: {
                key: _summarize(values)
                for key, values in sorted(metrics.items())
            }
            for bucket, metrics in sorted(by_bucket.items())
        },
    }


def _space_event_promotion_gate(aggregate: dict[str, Any]) -> dict[str, Any]:
    minimum = SPACE_CATALYST_PROMOTION_GATES["minimum_closed_decisions"]
    overall = aggregate.get("overall") or {}
    closed = int(aggregate.get("closed_decision_count") or 0)
    official_closed = int(aggregate.get("official_closed_decision_count") or 0)
    checks = {
        "minimum_closed_decisions": closed >= minimum,
        "official_bucket_has_closed_decision": official_closed > 0,
        "positive_10d_return": _avg_positive(overall.get("10d_return")),
        "positive_10d_same_theme_value": _avg_positive(
            overall.get("10d_same_theme_value")
        ),
        "positive_10d_ufo_relative_value": _avg_positive(
            overall.get("10d_ufo_relative_value")
        ),
        "positive_10d_arkx_relative_value": _avg_positive(
            overall.get("10d_arkx_relative_value")
        ),
    }
    passed = all(checks.values())
    return {
        "passed": passed,
        "mode": "observe_only",
        "checks": checks,
        "closed_decision_count": closed,
        "official_closed_decision_count": official_closed,
        "minimum_closed_decisions": minimum,
        "reason": (
            "passed_forward_gate"
            if passed
            else "insufficient_closed_official_forward_replacement_value"
        ),
    }


def _empty_event_aggregate() -> dict[str, Any]:
    return {
        "event_row_count": 0,
        "closed_decision_count": 0,
        "official_closed_decision_count": 0,
        "attention_only_closed_decision_count": 0,
        "pending_decision_count": 0,
        "by_semantic_bucket_count": {},
        "overall": {},
        "by_semantic_bucket": {},
    }


def _same_theme_tickers(space_catalyst_shadow: dict[str, Any] | None) -> list[str]:
    tickers = set()
    shadow = space_catalyst_shadow or {}
    for ticker in (shadow.get("forward_hypothesis") or {}).get("included_tickers") or []:
        tickers.add(str(ticker).upper())
    for segment, segment_tickers in (shadow.get("tickers_by_segment") or {}).items():
        if str(segment) in SPACE_CATALYST_NON_OPERATING_SEGMENTS:
            continue
        for ticker in segment_tickers or []:
            tickers.add(str(ticker).upper())
    return sorted(ticker for ticker in tickers if ticker)


def _theme_segment_for_ticker(space_catalyst_shadow: dict[str, Any], ticker: str) -> str | None:
    for segment, tickers in (space_catalyst_shadow.get("tickers_by_segment") or {}).items():
        if ticker in {str(item).upper() for item in tickers or []}:
            return str(segment)
    return None


def _same_day_core_alternatives(
    core_signals: list[dict[str, Any]],
    entry_execution_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for rank, signal in enumerate(core_signals or [], start=1):
        if isinstance(signal, dict):
            rows.append(_compact_signal(signal, rank=rank, source="selected_core_signal"))
    for signal in entry_execution_plan.get("deferred_breakout_signals") or []:
        if isinstance(signal, dict):
            rows.append(
                _compact_signal(
                    signal,
                    rank=signal.get("candidate_rank"),
                    source="deferred_breakout_signal",
                )
            )
    for rank, signal in enumerate(entry_execution_plan.get("slot_sliced_signals") or [], start=1):
        if isinstance(signal, dict):
            rows.append(
                _compact_signal(
                    signal,
                    rank=signal.get("candidate_rank", rank),
                    source="slot_sliced_signal",
                )
            )
    return [row for row in rows if row.get("ticker")]


def _compact_signal(signal: dict[str, Any], *, rank: Any, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "rank": rank,
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": signal.get("strategy"),
        "action": signal.get("action"),
        "sector": signal.get("sector"),
        "entry_price": _round(signal.get("entry_price"), 4),
        "confidence_score": _round(signal.get("confidence_score"), 4),
        "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
    }


def _ticker_return(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    ticker = str(ticker or "").upper()
    closes = {row["date"]: row["close"] for row in rows_by_ticker.get(ticker) or []}
    start = closes.get(start_date)
    end = closes.get(end_date)
    if start is None or end is None or start <= 0:
        return {
            "return": None,
            "pnl_proxy": None,
            "available": False,
            "missing_reason": "missing_start_or_end_close",
        }
    ret = (end / start) - 1.0
    return {
        "return": _round(ret),
        "pnl_proxy": _round(ret * SPACE_CATALYST_EVENT_INITIAL_NOTIONAL, 2),
        "available": True,
    }


def _basket_return(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    tickers: list[str],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    returns = {}
    missing = []
    for ticker in sorted({str(item).upper() for item in tickers or [] if item}):
        result = _ticker_return(rows_by_ticker, ticker, start_date, end_date)
        if result.get("return") is None:
            missing.append(ticker)
        else:
            returns[ticker] = float(result["return"])
    if not returns:
        return {
            "return": None,
            "pnl_proxy": None,
            "available_tickers": [],
            "missing_tickers": missing,
        }
    avg_return = mean(returns.values())
    return {
        "return": _round(avg_return),
        "pnl_proxy": _round(avg_return * SPACE_CATALYST_EVENT_INITIAL_NOTIONAL, 2),
        "available_tickers": sorted(returns),
        "missing_tickers": sorted(missing),
        "ticker_returns": {ticker: _round(value) for ticker, value in sorted(returns.items())},
    }


def _normalise_ohlcv_rows(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if hasattr(raw, "reset_index") and hasattr(raw, "to_dict"):
        records = raw.reset_index().to_dict("records")
    elif isinstance(raw, dict) and "rows" in raw:
        records = raw.get("rows") or []
    elif isinstance(raw, dict) and "data" in raw:
        records = raw.get("data") or []
    elif isinstance(raw, list):
        records = raw
    else:
        return []
    rows = []
    for item in records:
        if not isinstance(item, dict):
            continue
        date_value = _date_from_row(item)
        close = _as_float(_first_present(item, ("Close", "close")))
        if not date_value or close is None or close <= 0:
            continue
        rows.append({"date": date_value, "close": close})
    return sorted(rows, key=lambda row: row["date"])


def _truncate_rows(rows: list[dict[str, Any]], asof_date: str) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("date") <= asof_date]


def _next_trading_date(rows: list[dict[str, Any]], event_date: str) -> str | None:
    for row in rows:
        date = row.get("date")
        if date and date > event_date:
            return date
    return None


def _horizon_date(rows: list[dict[str, Any]], entry_date: str, horizon: int) -> str | None:
    dates = [row.get("date") for row in rows]
    try:
        idx = dates.index(entry_date)
    except ValueError:
        return None
    target_idx = idx + horizon
    if target_idx >= len(dates):
        return None
    return dates[target_idx]


def _date_from_row(row: dict[str, Any]) -> str | None:
    raw = _first_present(row, ("Date", "date", "Datetime", "datetime", "index"))
    if raw is None:
        return None
    if hasattr(raw, "date"):
        return raw.date().isoformat()
    text = str(raw)
    return text[:10] if len(text) >= 10 else None


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _round(value: Any, digits: int = 6) -> Any:
    out = _as_float(value)
    return round(out, digits) if out is not None else None


def _summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg": None, "median": None, "win_rate": None}
    return {
        "count": len(values),
        "avg": _round(mean(values)),
        "median": _round(median(values)),
        "win_rate": _round(sum(1 for value in values if value > 0) / len(values), 4),
    }


def _avg_positive(summary: dict[str, Any] | None) -> bool:
    avg = _as_float((summary or {}).get("avg"))
    return avg is not None and avg > 0


def _event_ledger_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("asof_date") or ""),
        str(row.get("event_id") or ""),
        str(row.get("ticker") or ""),
        SPACE_CATALYST_EVENT_LEDGER_RULE_VERSION,
    )


def _event_ledger_keys(path: Path) -> set[tuple[str, str, str, str]]:
    return {_event_ledger_key(row) for row in _read_jsonl_rows(path)}


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _event_ledger_production_impact() -> dict[str, bool]:
    return {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "parity_test_added": False,
        "replay_only": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
    }
