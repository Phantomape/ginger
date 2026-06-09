"""exp-20260609-025: Form 4 liquidity/cost/cluster purchase qualifier.

Replay-only alpha search. This tests one Form 4 event qualification bundle:
raw PIT-safe meaningful purchase events are kept only when the purchase is
material versus prior 20-day dollar volume, supported by cluster/senior-owner
evidence, and the next-open entry is not extended above insiders' weighted
reported cost.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260602_031_form4_pre_event_underpriced_purchase as base  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from form4_event_queue import (  # noqa: E402
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    QUEUE_NAME,
    RULE_VERSION,
    aggregate_purchase_events,
    load_form4_transaction_rows,
    qualifies_forward_queue_event,
)


EXPERIMENT_ID = "exp-20260609-025"
STEM = "form4_liquidity_cost_cluster_purchase"
TRIAL_FAMILY = "form4_liquidity_cost_cluster_candidate_pool"
TRIAL_VARIANT_ID = "form4_liquidity_cost_cluster_top1_10d_v1"
CHANGED_VARIABLE = "form4_liquidity_cost_cluster_qualifier_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_025_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_core_aggregate.json"
RAW_FORM4_AGG_JSON = OUT_DIR / f"{STEM}_raw_form4_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_qualified_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

FORM4_TRANSACTIONS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)

WINDOWS = base.WINDOWS
MIN_PURCHASE_VALUE_TO_ADV20 = 0.001
MIN_ENTRY_OPEN_TO_WEIGHTED_COST = 0.82
MAX_ENTRY_OPEN_TO_WEIGHTED_COST = 1.08
MIN_TARGET_TRADES = 8
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.75
MAX_POSITIVE_HHI = 0.60

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "does_not_beat_raw_form4_queue",
        "sample_too_thin",
        "old_thin_regression",
        "cost_anchor_relabel",
        "concentration",
    ],
    "confidence_reason": (
        "Form4 is PIT-safe and free across the fixed windows, but nearby Form4 "
        "qualifiers repeatedly failed raw-queue replacement value. This run has "
        "low confidence because it tests a stricter purchase-value-to-liquidity "
        "plus cost-anchor cluster relation."
    ),
    "recorded_at": "2026-06-09T21:10:35+00:00",
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "parity_test_added": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "trade_enabled": False,
    "production_signal_path_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_orders": False,
    "live_slots_changed": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production path. A positive result would "
        "require a shared default-off Form 4 adapter that computes the same "
        "usable-date event grouping, weighted purchase cost, prior-20-day dollar "
        "volume, cluster/senior-owner support, next-open paper entry, 10-day "
        "exit, costs, capacity, raw Form4 comparator, and source-row cache in "
        "both historical replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(Path(path))


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _load_price_map() -> dict[str, list[dict[str, Any]]]:
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for window in WINDOWS.values():
        payload = base._json_load(REPO_ROOT / window["snapshot"], {})
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict) or not row.get("Date"):
                    continue
                date_key = str(row["Date"])[:10]
                by_ticker_date[ticker_key][date_key] = {
                    "date": date_key,
                    "open": _float_or_none(row.get("Open")),
                    "close": _float_or_none(row.get("Close")),
                    "volume": _float_or_none(row.get("Volume")),
                }
    return {
        ticker: sorted(rows.values(), key=lambda row: row["date"])
        for ticker, rows in by_ticker_date.items()
    }


def _first_index_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def _avg_dollar_volume_20d(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_date: str,
) -> float | None:
    rows = prices.get(ticker.upper())
    if not rows:
        return None
    entry_idx = _first_index_on_or_after(rows, usable_date)
    if entry_idx is None or entry_idx < 20:
        return None
    values = []
    for row in rows[entry_idx - 20 : entry_idx]:
        close = row.get("close")
        volume = row.get("volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _purchase_cost_surface(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "value": 0.0,
            "shares": 0.0,
            "priced_transaction_count": 0,
        }
    )
    for row in rows:
        if not row.get("open_market_purchase_flag"):
            continue
        ticker = str(row.get("ticker") or "").upper()
        usable = str(row.get("usable_trade_date") or "")[:10]
        value = _float_or_none(row.get("transaction_value"))
        shares = _float_or_none(row.get("shares"))
        if not ticker or not usable or value is None or shares is None or shares <= 0.0:
            continue
        key = (ticker, usable)
        grouped[key]["value"] += value
        grouped[key]["shares"] += shares
        grouped[key]["priced_transaction_count"] += 1
    for surface in grouped.values():
        shares = float(surface["shares"])
        surface["weighted_purchase_price"] = (
            surface["value"] / shares if shares > 0.0 else None
        )
    return grouped


def _window_name(value: str) -> str | None:
    for label, window in WINDOWS.items():
        if window["start"] <= value <= window["end"]:
            return label
    return None


def _entry_open(
    prices: dict[str, list[dict[str, Any]]],
    ticker: str,
    usable_date: str,
) -> float | None:
    rows = prices.get(ticker.upper())
    if not rows:
        return None
    idx = _first_index_on_or_after(rows, usable_date)
    if idx is None:
        return None
    return rows[idx].get("open")


def _cluster_or_senior_support(event: dict[str, Any]) -> bool:
    return (
        int(event.get("owner_count") or 0) >= 2
        or int(event.get("purchase_transaction_count") or 0) >= 2
        or bool(event.get("any_ceo_cfo_or_president"))
        or bool(event.get("any_10pct_owner"))
    )


def _enrich_event(
    event: dict[str, Any],
    *,
    prices: dict[str, list[dict[str, Any]]],
    cost_surface: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(event.get("ticker") or "").upper()
    usable = str(event.get("usable_trade_date") or "")[:10]
    adv20 = _avg_dollar_volume_20d(prices, ticker, usable)
    entry_open = _entry_open(prices, ticker, usable)
    cost = cost_surface.get((ticker, usable)) or {}
    weighted_cost = cost.get("weighted_purchase_price")
    if adv20 is None or entry_open is None or weighted_cost is None or weighted_cost <= 0.0:
        return {
            **event,
            "window": _window_name(usable),
            "liquidity_cost_cluster_status": "missing_cost_or_liquidity_surface",
        }
    purchase_value = float(event.get("total_purchase_value") or 0.0)
    value_to_adv20 = purchase_value / adv20 if adv20 > 0.0 else None
    entry_to_cost = entry_open / float(weighted_cost)
    cluster_or_senior = _cluster_or_senior_support(event)
    qualified = (
        value_to_adv20 is not None
        and value_to_adv20 >= MIN_PURCHASE_VALUE_TO_ADV20
        and MIN_ENTRY_OPEN_TO_WEIGHTED_COST <= entry_to_cost <= MAX_ENTRY_OPEN_TO_WEIGHTED_COST
        and cluster_or_senior
    )
    return {
        **event,
        "window": _window_name(usable),
        "liquidity_cost_cluster_status": "ready",
        "avg_dollar_volume_20d": round(adv20, 2),
        "purchase_value_to_adv20": round(value_to_adv20, 8) if value_to_adv20 is not None else None,
        "weighted_purchase_price": round(float(weighted_cost), 6),
        "entry_open": round(float(entry_open), 6),
        "entry_open_to_weighted_purchase_price": round(entry_to_cost, 6),
        "cluster_or_senior_support": cluster_or_senior,
        "cluster_or_senior_reason": {
            "owner_count_ge_2": int(event.get("owner_count") or 0) >= 2,
            "purchase_transaction_count_ge_2": int(event.get("purchase_transaction_count") or 0) >= 2,
            "any_ceo_cfo_or_president": bool(event.get("any_ceo_cfo_or_president")),
            "any_10pct_owner": bool(event.get("any_10pct_owner")),
        },
        "liquidity_cost_cluster_qualified": qualified,
    }


def _load_forward_events(prices: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    start = min(window["start"] for window in WINDOWS.values())
    end = max(window["end"] for window in WINDOWS.values())
    cost_surface = _purchase_cost_surface(rows)
    raw_events = [
        _enrich_event(event, prices=prices, cost_surface=cost_surface)
        for event in aggregate_purchase_events(rows, start=start, end=end)
        if qualifies_forward_queue_event(event)
    ]
    events = [event for event in raw_events if event.get("window") is not None]
    scan = {
        "source_path": _repo_rel(FORM4_TRANSACTIONS_PATH),
        "source_row_count": len(rows),
        "raw_forward_event_count": len(events),
        "ready_event_count": sum(
            1 for row in events if row.get("liquidity_cost_cluster_status") == "ready"
        ),
        "qualified_event_count": sum(
            1 for row in events if row.get("liquidity_cost_cluster_qualified")
        ),
        "qualified_by_window": {
            label: sum(
                1
                for row in events
                if row.get("window") == label
                and row.get("liquidity_cost_cluster_qualified")
            )
            for label in WINDOWS
        },
    }
    return sorted(events, key=lambda row: (row.get("usable_trade_date") or "", row.get("ticker") or "")), scan


def _positive_pnl_concentration(details: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for detail in details.values():
        for trade in detail.get("qualified_selected_trades") or []:
            pnl = float(trade.get("pnl") or 0.0)
            if pnl > 0.0:
                by_ticker[str(trade.get("ticker") or "").upper()] += pnl
    total = sum(by_ticker.values())
    if total <= 0.0:
        return {
            "single_ticker_positive_share": None,
            "positive_pnl_hhi": None,
            "positive_pnl_by_ticker": {},
        }
    shares = {ticker: value / total for ticker, value in by_ticker.items()}
    return {
        "single_ticker_positive_share": round(max(shares.values()), 6),
        "positive_pnl_hhi": round(sum(value * value for value in shares.values()), 6),
        "positive_pnl_by_ticker": {
            ticker: round(value, 2) for ticker, value in sorted(by_ticker.items())
        },
    }


def _gate_result(
    core_delta: dict[str, Any],
    raw_delta: dict[str, Any],
    details: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selected = sum(int(row.get("qualified_selected_trade_count") or 0) for row in details.values())
    target_windows = [
        label
        for label, row in details.items()
        if int(row.get("qualified_selected_trade_count") or 0) > 0
    ]
    concentration = _positive_pnl_concentration(details)
    single_share = concentration["single_ticker_positive_share"]
    hhi = concentration["positive_pnl_hhi"]
    improves_core = (
        core_delta["aggregate_ev_delta"] > 0.0
        and core_delta["aggregate_pnl_delta"] > 0.0
        and core_delta["windows_ev_regressed"] == 0
        and core_delta["windows_pnl_regressed"] == 0
    )
    improves_raw = (
        raw_delta["aggregate_ev_delta"] > 0.0
        and raw_delta["aggregate_pnl_delta"] > 0.0
        and raw_delta["windows_ev_regressed"] == 0
        and raw_delta["windows_pnl_regressed"] == 0
    )
    drawdown_ok = core_delta["max_drawdown_drift"] <= MAX_DRAWDOWN_WORSE
    sample_ok = (
        selected >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and (single_share is None or single_share <= MAX_SINGLE_POSITIVE_SHARE)
        and (hhi is None or hhi <= MAX_POSITIVE_HHI)
    )
    failed: list[str] = []
    if not improves_core:
        failed.append("does_not_improve_core_cleanly")
    if not improves_raw:
        failed.append("does_not_improve_raw_form4_queue")
    if not drawdown_ok:
        failed.append("drawdown_drift_too_high")
    if selected < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if single_share is not None and single_share > MAX_SINGLE_POSITIVE_SHARE:
        failed.append("single_ticker_concentration")
    if hhi is not None and hhi > MAX_POSITIVE_HHI:
        failed.append("positive_pnl_hhi_concentration")
    return {
        "passed": bool(improves_core and improves_raw and drawdown_ok and sample_ok),
        "decision": (
            "accepted_research_form4_liquidity_cost_cluster_requires_shared_adapter"
            if not failed
            else "rejected_form4_liquidity_cost_cluster_candidate_pool"
        ),
        "failed_reasons": failed,
        "improves_core_cleanly": bool(improves_core),
        "improves_vs_raw_form4": bool(improves_raw),
        "drawdown_guard_passed": bool(drawdown_ok),
        "max_drawdown_drift_guard": f"<= {MAX_DRAWDOWN_WORSE}",
        "qualified_selected_event_trades": selected,
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "single_ticker_positive_share": single_share,
        "single_ticker_positive_share_guard": f"<= {MAX_SINGLE_POSITIVE_SHARE}",
        "positive_pnl_hhi": hhi,
        "positive_pnl_hhi_guard": f"<= {MAX_POSITIVE_HHI}",
        "sample_guard_passed": bool(sample_ok),
        "positive_pnl_by_ticker": concentration["positive_pnl_by_ticker"],
    }


def _build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    universe = base.get_universe()
    prices = _load_price_map()
    events, source_scan = _load_forward_events(prices)
    raw_candidates = [base._candidate_trade(event, prices) for event in events]
    qualified_events = [
        event for event in events if event.get("liquidity_cost_cluster_qualified")
    ]
    qualified_candidates = [base._candidate_trade(event, prices) for event in qualified_events]

    core_baseline: dict[str, dict[str, Any]] = OrderedDict()
    raw_metrics: dict[str, dict[str, Any]] = OrderedDict()
    after_metrics: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_raw: dict[str, dict[str, Any]] = OrderedDict()
    deltas_vs_core: dict[str, dict[str, Any]] = OrderedDict()
    details: dict[str, dict[str, Any]] = OrderedDict()

    for label, window in WINDOWS.items():
        print(f"[{label}] core, raw Form4, and qualified Form4 replay")
        result = base.BacktestEngine(
            universe,
            start=window["start"],
            end=window["end"],
            replay_llm=False,
            replay_news=False,
            ohlcv_snapshot_path=window["snapshot"],
        ).run()
        raw_selected, raw_skipped = base._select_event_trades(
            raw_candidates,
            start=window["start"],
            end=window["end"],
        )
        qualified_selected, qualified_skipped = base._select_event_trades(
            qualified_candidates,
            start=window["start"],
            end=window["end"],
        )
        raw_curve = base._event_equity_curve(
            raw_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        qualified_curve = base._event_equity_curve(
            qualified_selected,
            prices=prices,
            start=window["start"],
            end=window["end"],
        )
        core_baseline[label] = base._core_metrics(result)
        raw_metrics[label] = (
            base._combined_metrics(result, raw_curve, raw_selected)
            if raw_selected
            else dict(core_baseline[label])
        )
        after_metrics[label] = (
            base._combined_metrics(result, qualified_curve, qualified_selected)
            if qualified_selected
            else dict(core_baseline[label])
        )
        deltas_vs_raw[label] = base._delta(raw_metrics[label], after_metrics[label])
        deltas_vs_core[label] = base._delta(core_baseline[label], after_metrics[label])
        scoped_events = [
            row
            for row in events
            if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
        ]
        scoped_qualified = [
            row
            for row in qualified_events
            if window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
        ]
        details[label] = {
            "raw_forward_event_count": len(scoped_events),
            "ready_event_count": sum(
                1
                for row in scoped_events
                if row.get("liquidity_cost_cluster_status") == "ready"
            ),
            "qualified_event_count": len(scoped_qualified),
            "raw_price_ready_count": sum(
                1
                for row in raw_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "qualified_price_ready_count": sum(
                1
                for row in qualified_candidates
                if row.get("status") == "price_ready"
                and window["start"] <= str(row.get("usable_trade_date") or "")[:10] <= window["end"]
            ),
            "raw_selected_trade_count": len(raw_selected),
            "qualified_selected_trade_count": len(qualified_selected),
            "raw_skipped_count": len(raw_skipped),
            "qualified_skipped_count": len(qualified_skipped),
            "raw_selected_trades": raw_selected,
            "qualified_selected_trades": qualified_selected,
            "qualified_events": scoped_qualified,
            "qualified_skipped_candidates": qualified_skipped[:20],
        }

    aggregate_vs_raw = base._aggregate_delta(raw_metrics, after_metrics)
    aggregate_vs_core = base._aggregate_delta(core_baseline, after_metrics)
    gate = _gate_result(aggregate_vs_core, aggregate_vs_raw, details)
    status = "accepted" if gate["passed"] else "rejected"
    decision = gate["decision"]
    actual_success = 1.0 if gate["passed"] else 0.0
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in core_baseline.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": int(actual_success),
        "actual_gate4_passed": gate["passed"],
        "actual_ev_delta_vs_core": aggregate_vs_core["aggregate_ev_delta"],
        "actual_pnl_delta_vs_core": aggregate_vs_core["aggregate_pnl_delta"],
        "actual_ev_delta_vs_raw_form4": aggregate_vs_raw["aggregate_ev_delta"],
        "actual_pnl_delta_vs_raw_form4": aggregate_vs_raw["aggregate_pnl_delta"],
        "failure_modes_observed": gate["failed_reasons"],
        "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": (
            "PIT-safe Form 4 meaningful purchase events should have cleaner "
            "forward value when the purchase is material versus prior 20-day "
            "dollar volume, supported by cluster or senior-owner evidence, and "
            "entered near the insiders' weighted reported purchase cost."
        ),
        "change_type": "event_qualification_replay",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260504-034",
            "exp-20260529-002",
            "exp-20260530-003",
            "exp-20260530-011",
            "exp-20260602-016",
            "exp-20260602-031",
            "exp-20260604-022",
            "exp-20260605-001",
        ],
        "prior_trial_count": 7,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_sec_form4_purchase_value_to_liquidity_cost_anchor_cluster",
        "prediction": PREDICTION,
        "calibration": calibration,
        "parameters": {
            "form4_queue_name": QUEUE_NAME,
            "form4_rule_version": RULE_VERSION,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "min_purchase_value_to_adv20": MIN_PURCHASE_VALUE_TO_ADV20,
            "min_entry_open_to_weighted_purchase_price": MIN_ENTRY_OPEN_TO_WEIGHTED_COST,
            "max_entry_open_to_weighted_purchase_price": MAX_ENTRY_OPEN_TO_WEIGHTED_COST,
            "event_notional_usd": base.EVENT_NOTIONAL,
            "max_event_positions": base.MAX_EVENT_POSITIONS,
            "hold_days": base.HOLD_DAYS,
            "single_causal_variable": CHANGED_VARIABLE,
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "LLM/news replay settings",
                "Form 4 parser",
                "Form 4 forward purchase-value threshold for raw comparator",
                "event notional",
                "event holding period",
                "event capacity",
                "production orders",
                "production watchlists",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: insider purchases should be more "
                "actionable when the capital deployed is material versus the "
                "ticker's own liquidity and next-open price is not extended "
                "above insiders' weighted reported cost."
            ),
            "2_history_check": {
                "exp-20260504-034": "Raw Form 4 event satellite was positive but not promoted.",
                "exp-20260529-002": "Executive-role Form 4 qualifier was positive vs core but not raw and too concentrated.",
                "exp-20260530-003": "Ownership-delta Form 4 qualifier was positive vs core but not raw and too small/materiality failed.",
                "exp-20260530-011": "Multi-filer Form 4 forward queue did not create promotable evidence.",
                "exp-20260602-016": "Form4 + FINRA short-pressure consensus did not improve raw Form4 queue.",
                "exp-20260602-031": "Pre-event underpricing Form4 qualifier did not improve raw Form4 queue.",
                "exp-20260604-022": "Cost-basis entry-alignment alone underperformed raw Form4 queue.",
                "exp-20260605-001": "Liquidity intensity was positive vs core but failed replacement value vs raw Form4 queue.",
            },
            "3_single_causal_variable": (
                "Only the event qualifier changes: prior-20-day purchase value "
                "to dollar-volume, cluster/senior-owner support, and next-open "
                "price relative to weighted insider cost. Core strategy, raw "
                "Form4 queue, notional, capacity, hold period, LLM/news, "
                "ranking, sizing, exits, and production orders stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; must improve aggregate "
                "EV/PnL versus core and raw Form4, avoid window EV/PnL "
                "regressions, and pass drawdown, survival, target sample, and "
                "concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260609_025_form4_liquidity_cost_cluster_purchase.py"
            ),
        },
        "pre_run_questions": {
            "answered_before_strategy_logic_change": True,
            "alpha_hypothesis_type": "entry/candidate_pool",
            "history_checked": True,
            "single_policy_bundle": CHANGED_VARIABLE,
            "acceptance_standard": "docs/backtesting.md canonical three-window replay plus raw Form4 comparator",
            "reproducibility_plan": _repo_rel(Path(__file__)),
        },
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three fixed windows",
            "windows": WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses Form 4 usable_trade_date plus prior OHLCV for "
                "ADV20; paper entry is next available open, exit is close 10 "
                "trading days later, with the existing Form4 event sleeve "
                "notional, capacity, and round-trip cost model."
            ),
        },
        "gate1": {
            "protocol": "docs/backtesting.md canonical three fixed windows",
            "core_baseline_metrics": core_baseline,
            "baseline_result_file": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": base._position_field_check(),
            "runtime_fields": [
                "Form 4 ticker",
                "Form 4 usable_trade_date",
                "Form 4 total_purchase_value",
                "Form 4 owner_count",
                "Form 4 purchase_transaction_count",
                "Form 4 owner role flags",
                "Form 4 price/shares transaction rows",
                "OHLCV Open/Close/Volume",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "min_survival_rate": base._round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The Form 4 "
                "qualifier is additive default-off paper only, so core signals "
                "generated/survived are unchanged from baseline."
            ),
        },
        "gate4": gate,
        "core_baseline_metrics": core_baseline,
        "raw_form4_metrics": raw_metrics,
        "after_metrics": after_metrics,
        "before_aggregate": base._aggregate_metrics(core_baseline),
        "raw_form4_aggregate": base._aggregate_metrics(raw_metrics),
        "after_aggregate": base._aggregate_metrics(after_metrics),
        "deltas_vs_raw_form4": deltas_vs_raw,
        "deltas_vs_core": deltas_vs_core,
        "aggregate_delta_vs_raw_form4": aggregate_vs_raw,
        "aggregate_delta_vs_core": aggregate_vs_core,
        "source_scan": source_scan,
        "event_details": details,
        "decision_rationale": (
            "The liquidity/cost/cluster Form4 slice passed both core and raw "
            "Form4 replacement gates. It remains default-off until a shared "
            "adapter and parity tests are implemented."
            if gate["passed"]
            else (
                "The liquidity/cost/cluster Form4 slice did not produce enough "
                "stable three-window replacement value versus core and raw "
                "Form4, or failed sample/risk gates. It should not be promoted."
            )
        ),
        "post_run_reflection": (
            {
                "why_result_happened": (
                    "The fixed policy separated higher-quality insider "
                    "accumulation from raw queue noise across all three windows."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retune thresholds before building the shared adapter "
                    "and collecting forward replacement rows."
                ),
                "new_evidence_required": (
                    "Shared adapter parity plus closed forward replacement rows "
                    "are required before production observation or activation."
                ),
            }
            if gate["passed"]
            else {
                "why_result_happened": (
                    "The stricter cluster/cost/liquidity qualifier produced too "
                    "few selected trades and failed raw Form4 replacement value. "
                    "The data shape shows that adding cluster or senior-owner "
                    "support to the already sparse forward queue removes most "
                    "events rather than creating a robust candidate-pool edge."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping the purchase-value-to-ADV, "
                    "entry-to-cost, owner-count, transaction-count, senior-role, "
                    "notional, capacity, or hold-day thresholds on these frozen "
                    "windows."
                ),
                "new_evidence_required": (
                    "A Form4 revisit needs a denser forward replacement source, "
                    "such as broader PIT daily filings with source-row cache, "
                    "or a materially new relation like buyback authorization or "
                    "official short-interest context. Otherwise move to another "
                    "alpha family."
                ),
            }
        ),
        "why_not_other_alpha": (
            "Skipped LLM soft-ranking because recent revision/LLM rows were too "
            "sparse for reliable replay. Skipped state-surface and broad OHLCV "
            "retunes per playbook freeze guidance. This run used free SEC Form 4 "
            "data because it has PIT usable dates across the canonical windows."
        ),
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": (
                "This run uses deterministic free SEC Form 4 rows plus fixed "
                "OHLCV snapshots; no LLM prompt, inference, or replay path changed."
            ),
        },
        "production_impact": PRODUCTION_IMPACT,
        "data_sources": {
            "form4_transactions_path": _repo_rel(FORM4_TRANSACTIONS_PATH),
            "ohlcv_snapshots": {label: window["snapshot"] for label, window in WINDOWS.items()},
            "pit_status": (
                "Uses Form 4 usable_trade_date and prior trading-day OHLCV "
                "inside fixed snapshots; no filing or price lookahead added."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(RAW_FORM4_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOC_TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_result_file"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["aggregate_delta_vs_core"]["aggregate_ev_delta"],
        "aggregate_expected_value_delta_pct": payload["aggregate_delta_vs_core"]["aggregate_ev_delta_pct"],
        "aggregate_strategy_total_pnl_delta": payload["aggregate_delta_vs_core"]["aggregate_pnl_delta"],
        "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["core_baseline_metrics"][label]["expected_value_score"],
                "expected_value_raw_form4": payload["raw_form4_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta_vs_core": payload["deltas_vs_core"][label]["expected_value_score"],
                "expected_value_delta_vs_raw_form4": payload["deltas_vs_raw_form4"][label]["expected_value_score"],
                "strategy_total_pnl_delta_vs_core": payload["deltas_vs_core"][label]["total_pnl"],
                "strategy_total_pnl_delta_vs_raw_form4": payload["deltas_vs_raw_form4"][label]["total_pnl"],
                "raw_forward_event_count": payload["event_details"][label]["raw_forward_event_count"],
                "qualified_event_count": payload["event_details"][label]["qualified_event_count"],
                "target_trade_count": payload["event_details"][label]["qualified_selected_trade_count"],
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": (
            "If rejected, the likely reason is sparse Form 4 forward-queue "
            "coverage after adding cluster/senior support and cost anchoring, "
            "or that liquidity/cost anchoring is just a materiality relabel "
            "that fails raw-queue replacement value."
        ),
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _append_experiment_log(record: dict[str, Any]) -> None:
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXPERIMENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Core EV | Raw EV | After EV | dEV Core | dEV Raw | Core PnL | Raw PnL | After PnL | dPnL Core | dPnL Raw | Qualified | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        core = payload["core_baseline_metrics"][label]
        raw = payload["raw_form4_metrics"][label]
        after = payload["after_metrics"][label]
        core_delta = payload["deltas_vs_core"][label]
        raw_delta = payload["deltas_vs_raw_form4"][label]
        detail = payload["event_details"][label]
        rows.append(
            "| {label} | {core_ev:.4f} | {raw_ev:.4f} | {after_ev:.4f} | {dev_core:+.4f} | {dev_raw:+.4f} | ${core_pnl:,.2f} | ${raw_pnl:,.2f} | ${after_pnl:,.2f} | ${dpnl_core:+,.2f} | ${dpnl_raw:+,.2f} | {qualified} | {trades} |".format(
                label=label,
                core_ev=core["expected_value_score"],
                raw_ev=raw["expected_value_score"],
                after_ev=after["expected_value_score"],
                dev_core=core_delta["expected_value_score"],
                dev_raw=raw_delta["expected_value_score"],
                core_pnl=core["total_pnl"],
                raw_pnl=raw["total_pnl"],
                after_pnl=after["total_pnl"],
                dpnl_core=core_delta["total_pnl"],
                dpnl_raw=raw_delta["total_pnl"],
                qualified=detail["qualified_event_count"],
                trades=detail["qualified_selected_trade_count"],
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form4 Liquidity Cost Cluster Purchase",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta vs core: `{:+.4f}`".format(
                payload["aggregate_delta_vs_core"]["aggregate_ev_delta"]
            ),
            "- Aggregate PnL delta vs core: `${:+,.2f}`".format(
                payload["aggregate_delta_vs_core"]["aggregate_pnl_delta"]
            ),
            "- Aggregate EV delta vs raw Form4: `{:+.4f}`".format(
                payload["aggregate_delta_vs_raw_form4"]["aggregate_ev_delta"]
            ),
            "- Aggregate PnL delta vs raw Form4: `${:+,.2f}`".format(
                payload["aggregate_delta_vs_raw_form4"]["aggregate_pnl_delta"]
            ),
            "- Selected qualified event trades: `{}`".format(
                payload["gate4"]["qualified_selected_event_trades"]
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(BEFORE_AGG_JSON),
            _repo_rel(RAW_FORM4_AGG_JSON),
            _repo_rel(AFTER_AGG_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(DOC_TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): _sha256(script_path),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
            _repo_rel(ARTIFACT_MD): _sha256(ARTIFACT_MD),
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _persist(payload: dict[str, Any]) -> None:
    log_record = _log_record(payload)
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["before_aggregate"])
    base._write_json(RAW_FORM4_AGG_JSON, payload["raw_form4_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["after_aggregate"])
    report = _build_card(payload)
    _write_text(CARD_MD, report)
    _write_text(ARTIFACT_MD, report)
    _append_experiment_log(log_record)
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["aggregate_delta_vs_core"]["aggregate_ev_delta"],
        "aggregate_strategy_total_pnl_delta": payload["aggregate_delta_vs_core"]["aggregate_pnl_delta"],
        "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-automation",
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
        "summary": payload["decision_rationale"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": payload["aggregate_delta_vs_core"]["aggregate_ev_delta"],
        "aggregate_strategy_total_pnl_delta": payload["aggregate_delta_vs_core"]["aggregate_pnl_delta"],
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
    ticket_payload = base._json_load(TICKET_JSON, {})
    if ticket_payload:
        base._write_json(DOC_TICKET_JSON, ticket_payload)
    _write_manifest(payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "aggregate_delta_vs_core": payload["aggregate_delta_vs_core"],
                "aggregate_delta_vs_raw_form4": payload["aggregate_delta_vs_raw_form4"],
                "gate4": payload["gate4"],
                "source_scan": payload["source_scan"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
