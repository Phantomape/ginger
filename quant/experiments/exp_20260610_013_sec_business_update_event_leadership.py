"""exp-20260610-013: SEC business-update event leadership candidate pool.

Replay-only alpha search. This tests one candidate-source variable: point-in-
time event snapshots with SEC 8-K Item 8.01, 7.01, or 1.01 business-update
events, filtered through liquid SPY-relative leadership before a top-1
next-open default-off paper entry with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import exp_20260609_026_turn_of_month_liquid_leadership as base


framework = base.framework

EXPERIMENT_ID = "exp-20260610-013"
STEM = "sec_business_update_event_leadership"
TRIAL_FAMILY = "sec_business_update_event_leadership_candidate_pool"
TRIAL_VARIANT_ID = "sec_business_update_event_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_business_update_event_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_013_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EVENT_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "events"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

BUSINESS_UPDATE_EVENT_SUBTYPES = ("8k_item_1_01", "8k_item_7_01", "8k_item_8_01")
EVENT_SUBTYPE_WEIGHTS = {
    "8k_item_1_01": 1.20,
    "8k_item_8_01": 1.00,
    "8k_item_7_01": 0.95,
}

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = base.ACCEPTED_COMPRESSION_COMPARATOR
BASE_GATE4 = base.BASE_GATE4
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "event_field_too_generic",
        "window_regression",
        "drawdown_drift",
        "compression_comparator_not_beaten",
        "thin_sample",
    ],
    "confidence_reason": (
        "Event snapshots cover all three canonical windows and SEC business-"
        "update 8-K items are production-visible free data, but prior observed-"
        "only event-sensitive universe work and catalyst dossier attempts were "
        "not enough to prove a tradable source. This scout checks whether "
        "same-day liquid leadership supplies the missing displacement edge."
    ),
    "recorded_at": "2026-06-10T11:05:42+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead. Promotion would require a shared default-off adapter "
        "that loads the same signal-date event snapshot, applies the same SEC "
        "8-K Item 8.01/7.01/1.01 subtype bundle, source-confidence and PIT "
        "checks, liquid sector-known stock universe, SPY-relative leadership "
        "gates, close-quality gates, same-ticker core-overlap exclusion, next-"
        "open paper entry, 10-trading-day exit, costs, cooldown, accepted "
        "compression comparator, and concentration controls in both historical "
        "replay and daily production before any report queue, paper ledger, "
        "candidate priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "entry/candidate_pool: PIT-safe SEC 8-K business-update events "
        "(Items 8.01, 7.01, and 1.01) paired with same-day liquid SPY-relative "
        "leadership may identify underreaction candidates whose next-open "
        "continuation adds replacement value. It uses only free event snapshots "
        "and OHLCV fields known before the paper entry."
    ),
    "2_history_check": {
        "exact_prior": (
            "Targeted search over docs/experiment_log.jsonl, docs/experiments, "
            "experiments/logs, docs/lessons, and quant/experiments found no "
            "direct Gate 4 strategy for signal-date 8-K Item 8.01/7.01/1.01 "
            "business-update events plus liquid leadership."
        ),
        "nearby_event_sensitive_universe": (
            "exp-20260509-023 was observed-only and scored event-sensitive "
            "liquidity universes, including 7.01/8.01, but did not test a "
            "three-window candidate source with next-open paper entry."
        ),
        "nearby_catalyst_dossiers": (
            "exp-20260525-030 and exp-20260525-033 were observed-only VCP "
            "event-context/dossier work and were not accepted as a tradable "
            "business-update source."
        ),
        "accepted_comparator": (
            "exp-20260608-013 accepted narrow-range compression as the current "
            "stock-candidate comparator. This scout must beat its EV and PnL "
            "deltas before it is worth shared adapter work."
        ),
        "frozen_lanes_avoided": (
            "No LLM soft ranking, pre-earnings DTE retry, 52-week source "
            "extension, accepted helper source-priority extension, Form4 retry, "
            "Companyfacts scalar mining, or state-surface notional/profile "
            "retune is involved."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: signal-date event snapshot SEC 8-K Item "
        "8.01/7.01/1.01 business-update subtype bundle, high confidence and "
        "PIT-complete checks, non-negative/no-warning event quality, liquid "
        "sector-known stock universe, existing 20d/60d SPY-relative leadership "
        "gates, same-ticker core-overlap exclusion, top-1 next-open paper "
        "entry, 10-day hold, cost, cooldown, and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as a positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and the accepted "
        "exp-20260608-013 compression comparator is beaten. It is not accepted "
        "into production without a shared default-off helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_013_sec_business_update_event_leadership.py"
    ),
}


_EVENT_CACHE: dict[str, dict[str, Any] | None] = {}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _snapshot_key(signal_date: str) -> str:
    return signal_date.replace("-", "")


def _compact_date(value: Any) -> str:
    return str(value).replace("-", "")


def _load_event_snapshot(signal_date: str) -> dict[str, Any] | None:
    key = _snapshot_key(signal_date)
    if key not in _EVENT_CACHE:
        path = EVENT_DIR / f"event_snapshot_{key}.json"
        if not path.exists():
            _EVENT_CACHE[key] = None
        else:
            _EVENT_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
    return _EVENT_CACHE[key]


def _quality_warnings(event: dict[str, Any]) -> list[Any]:
    flags = event.get("quality_flags") or {}
    warnings = flags.get("warning") or []
    if isinstance(warnings, list):
        return warnings
    return [warnings]


def _event_title(event: dict[str, Any]) -> str | None:
    attrs = event.get("attributes") or {}
    title = attrs.get("title")
    if title is None:
        return None
    return str(title)


def _business_update_events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    snapshot = _load_event_snapshot(signal_date)
    if not snapshot:
        return {}

    signal_key = _snapshot_key(signal_date)
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, events in (snapshot.get("events_by_ticker") or {}).items():
        kept: list[dict[str, Any]] = []
        for event in events or []:
            subtype = event.get("event_subtype")
            if subtype not in BUSINESS_UPDATE_EVENT_SUBTYPES:
                continue
            if event.get("source_confidence") != "high":
                continue
            if not event.get("point_in_time_complete"):
                continue
            if event.get("surprise_direction") == "negative":
                continue
            if _quality_warnings(event):
                continue
            attrs = event.get("attributes") or {}
            if attrs.get("filing_type") != "8-K":
                continue
            if attrs.get("raw_source") != "sec_filing_text":
                continue
            usable_trade_date = attrs.get("usable_trade_date")
            if usable_trade_date is not None and _compact_date(usable_trade_date) != signal_key:
                continue
            kept.append(event)
        if kept:
            out[ticker] = kept
    return out


def _business_update_event_score(events: list[dict[str, Any]]) -> float:
    if not events:
        return 0.0
    subtype_score = max(
        EVENT_SUBTYPE_WEIGHTS.get(str(event.get("event_subtype")), 0.0)
        for event in events
    )
    subtype_count = len({str(event.get("event_subtype")) for event in events})
    duplicate_bonus = min(max(len(events) - 1, 0), 2) * 0.08
    subtype_diversity_bonus = max(subtype_count - 1, 0) * 0.05
    positive_hint_bonus = 0.0
    for event in events:
        if event.get("surprise_direction") == "positive":
            positive_hint_bonus = 0.10
            break
        flags = event.get("quality_flags") or {}
        positives = flags.get("positive") or []
        if positives:
            positive_hint_bonus = 0.10
            break
    return round(
        subtype_score + duplicate_bonus + subtype_diversity_bonus + positive_hint_bonus,
        6,
    )


def _candidate_for_business_update_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    row = base._candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        month_label="sec_business_update_event",
    )
    if row is None:
        return None

    subtypes = sorted({str(event.get("event_subtype")) for event in events})
    titles = [_event_title(event) for event in events]
    titles = [title for title in titles if title]
    event_score = _business_update_event_score(events)
    row["source"] = "SEC_BUSINESS_UPDATE_EVENT_LEADERSHIP_PAPER"
    row.pop("candidate_month_label", None)
    row["candidate_business_update_event_score"] = event_score
    row["candidate_business_update_event_subtypes"] = subtypes
    row["candidate_business_update_event_count"] = len(events)
    row["candidate_business_update_event_titles"] = titles[:3]
    row["candidate_event_snapshot_date"] = _snapshot_key(signal_date)
    row["uses_free_ohlcv_only"] = False
    row["uses_free_event_snapshot"] = True
    row["known_at"] = "signal_date_event_snapshot_and_ohlcv_before_next_open_paper_entry"
    row["rule_version"] = RULE_VERSION
    return row


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    all_dates = framework.shadow._trading_dates(snapshot)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    subtype_distribution: dict[str, int] = {}
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_event_snapshot": 0,
        "days_without_event_snapshot": 0,
        "days_with_business_update_event_tickers": 0,
        "business_update_event_tickers": 0,
        "days_with_raw_business_update_candidates": 0,
        "raw_business_update_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
    }

    for signal_date in dates:
        event_snapshot = _load_event_snapshot(signal_date)
        if event_snapshot is None:
            scan["days_without_event_snapshot"] += 1
            continue
        scan["days_with_event_snapshot"] += 1
        events_by_ticker = _business_update_events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_business_update_event_tickers"] += 1
        scan["business_update_event_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_business_update_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                continue
            for subtype in row["candidate_business_update_event_subtypes"]:
                subtype_distribution[subtype] = subtype_distribution.get(subtype, 0) + 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_business_update_event_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_business_update_candidates"] += 1
        scan["raw_business_update_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_business_update_event_score": top[
                    "candidate_business_update_event_score"
                ],
                "top_candidate_business_update_event_subtypes": top[
                    "candidate_business_update_event_subtypes"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_business_update_event_score"]),
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "event_subtype_distribution": dict(sorted(subtype_distribution.items())),
            "business_update_event_subtypes": list(BUSINESS_UPDATE_EVENT_SUBTYPES),
            "event_subtype_weights": EVENT_SUBTYPE_WEIGHTS,
            "source_confidence_required": "high",
            "point_in_time_complete_required": True,
            "negative_surprise_direction_excluded": True,
            "quality_warning_events_excluded": True,
            "min_price": base.MIN_PRICE,
            "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
            "min_signal_return": base.MIN_SIGNAL_RETURN,
            "min_close_location": base.MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
            "min_ret5": base.MIN_RET5,
            "max_ret5": base.MAX_RET5,
            "max_ret20": base.MAX_RET20,
            "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_business_update_event_leadership"
        if gate["passed"]
        else "rejected_sec_business_update_event_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only the signal-date event snapshot plus close-of-day OHLCV "
        "available on the signal date. Paper entry is next available open with "
        "existing entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_event_ohlcv_candidate_pool",
            "new_evidence_type": (
                "production_visible_free_sec_8k_business_update_event_snapshot_plus_ohlcv_leadership"
            ),
            "nearby_prior_experiments": [
                "exp-20260509-023",
                "exp-20260525-030",
                "exp-20260525-033",
                "exp-20260608-013",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that SEC business-update "
                "item labels are too generic: 8.01 and 7.01 often encode "
                "administrative disclosure instead of economically novel "
                "news, while 1.01 can be known or idiosyncratic. Leadership "
                "filters may still select generic momentum rather than "
                "post-disclosure underreaction. Do not answer by sweeping "
                "subtype weights, RS thresholds, close-location, top-N, hold-"
                "day, cooldown, or notional on these frozen windows without a "
                "richer PIT event-strength field."
            ),
            "next_evidence_needed": (
                "A retry needs materially richer free PIT event evidence, such "
                "as parsed agreement/product/customer/buyback/guidance "
                "semantics from the filing text, event-time before/after close "
                "verification, or a shared daily snapshot field that separates "
                "economically material 8-K business updates from generic Item "
                "8.01/7.01 filings. Pure subtype or momentum threshold tuning "
                "stays frozen."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "business_update_event_subtypes": list(BUSINESS_UPDATE_EVENT_SUBTYPES),
        "event_subtype_weights": EVENT_SUBTYPE_WEIGHTS,
        "source_confidence_required": "high",
        "point_in_time_complete_required": True,
        "negative_surprise_direction_excluded": True,
        "quality_warning_events_excluded": True,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
        "min_ret5": base.MIN_RET5,
        "max_ret5": base.MAX_RET5,
        "max_ret20": base.MAX_RET20,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "same_ticker_core_overlap_excluded": True,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed SEC business-update event leadership bundle cleared the "
            "canonical three-window gates and beat the accepted compression "
            "comparator, suggesting free PIT 8-K business-update events plus "
            "liquid leadership contributed replacement value beyond generic "
            "OHLCV compression. It remains only a replay lead because no "
            "shared daily adapter or production parity path was added."
            if passed
            else (
                "The fixed SEC business-update event leadership bundle failed "
                "Gate 4. The result implies the broad 8-K Item 8.01/7.01/1.01 "
                "labels did not add enough distinct edge beyond liquid "
                "momentum after next-open execution, costs, 10-day hold, "
                "cooldown, and overlap/concentration controls. The useful "
                "lesson is to seek richer PIT event-strength classification, "
                "not more item-code or momentum threshold tuning."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SEC item weights, item subsets, ret20/"
            "ret60 relative-strength thresholds, signal-day return, close-"
            "location, volume-ratio bounds, top-N, hold-day, cooldown, or "
            "paper notional on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC business-update event leadership source passed as a replay-"
        "only promotion lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The SEC business-update event leadership source was rejected; it "
            "did not establish a distinct free SEC event/OHLCV candidate-pool "
            "edge under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Event days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {event_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                event_days=scan.get("days_with_business_update_event_tickers", 0),
                days=scan.get("days_with_raw_business_update_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Business-Update Event Leadership Candidate Pool",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "mechanism_family": "production_visible_free_sec_event_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "business_update_event_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_business_update_event_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_business_update_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
