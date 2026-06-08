"""exp-20260608-027: SEC-event-provenanced peer shock candidate pool.

Replay-only alpha search. This tests one free PIT data edge: a whitelisted SEC
8-K event that is usable by the signal date and confirmed by a liquid anchor
price/volume shock may make rolling-correlation peer shock candidates cleaner
than broad peer matching.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import exp_20260606_018_rolling_corr_peer_shock_lag_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-027"
STEM = "sec_event_provenanced_peer_shock"
TRIAL_FAMILY = "sec_event_provenanced_peer_shock"
TRIAL_VARIANT_ID = "sec_event_provenanced_peer_shock_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_event_provenanced_rolling_corr_peer_shock_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_027_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_EVENTS_DIR = REPO_ROOT / "data" / "non_ohlcv"

ACCEPTED_PEER_SHOCK_EXPERIMENT_ID = "exp-20260606-025"
ACCEPTED_PEER_SHOCK_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_PEER_SHOCK_EXPERIMENT_ID
    / "exp_20260606_025_rolling_corr_peer_shock_shared_adapter.json"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

CORR_LOOKBACK_DAYS = previous.CORR_LOOKBACK_DAYS
MIN_CORRELATION = previous.MIN_CORRELATION
MAX_EVENT_ANCHORS_PER_DAY = 10
MAX_LAGGARD_CANDIDATES_PER_DAY = previous.MAX_LAGGARD_CANDIDATES_PER_DAY
MAX_RAW_ROWS_PER_DAY = previous.MAX_RAW_ROWS_PER_DAY

MIN_CANDIDATE_SIGNAL_RETURN = 0.000
MAX_CANDIDATE_SIGNAL_RETURN = 0.025
MIN_EVENT_PEER_SCORE = 0.0

EVENT_ITEM_WHITELIST = {"1.01", "2.02", "7.01", "8.01"}
EVENT_FORM_BASE_WHITELIST = {"8-K"}
EVENT_ITEM_BONUS = {"2.02": 0.09, "1.01": 0.07, "8.01": 0.04, "7.01": 0.03}

EXCLUDED_TICKERS = {
    "ARKK",
    "ARKX",
    "BIL",
    "CPER",
    "DIA",
    "GBTC",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "JNK",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXM",
    "VIXY",
    "VXX",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "sample_too_thin",
        "old_thin_regression",
        "drawdown_drift",
        "SEC_item_noise",
        "not_incremental_vs_accepted_peer_shock",
    ],
    "confidence_reason": (
        "Accepted rolling-correlation peer shock was strong, but broad sector "
        "and characteristic peer transfer recently failed. A PIT SEC event "
        "anchor is materially new free provenance that may improve relation "
        "quality, with clear risk of sparse or noisy 8-K item semantics."
    ),
    "recorded_at": "2026-06-08T23:08:10Z",
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
    "live_realism_evaluated": False,
    "live_ready": False,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain a replay lead until a shared default-off adapter computes the "
        "same SEC usable_trade_date filter, event item whitelist, anchor "
        "price/volume confirmation, rolling-correlation relation, candidate "
        "gates, next-open paper entry, 10-trading-day exit, costs, cooldown, "
        "core-overlap exclusion, comparator, and concentration controls in "
        "both historical replay and daily production."
    ),
}

BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_GATE4 = previous.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _event_file_for_date(signal_date: str) -> Path:
    return SEC_EVENTS_DIR / f"sec_filing_events_{signal_date.replace('-', '')}.jsonl"


def _event_items(row: dict[str, Any]) -> list[str]:
    raw_items = row.get("eight_k_item_codes")
    if isinstance(raw_items, list):
        return [str(item).strip() for item in raw_items if str(item).strip()]
    items_raw = str(row.get("items_raw") or "")
    return [item.strip() for item in items_raw.split(",") if item.strip()]


def _event_bonus(items: list[str]) -> float:
    return sum(EVENT_ITEM_BONUS.get(item, 0.0) for item in set(items))


@lru_cache(maxsize=512)
def _sec_events_by_ticker(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    path = _event_file_for_date(signal_date)
    if not path.exists():
        return {}
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if not ticker or ticker in EXCLUDED_TICKERS:
            continue
        if row.get("pit_safe_flag") is not True:
            continue
        if str(row.get("usable_trade_date") or "") != signal_date:
            continue
        form_base = str(row.get("form_base") or row.get("form_type") or "").upper()
        if form_base not in EVENT_FORM_BASE_WHITELIST:
            continue
        items = _event_items(row)
        if not EVENT_ITEM_WHITELIST.intersection(items):
            continue
        context = {
            "ticker": ticker,
            "accession_number": row.get("accession_number"),
            "form_type": row.get("form_type"),
            "form_base": row.get("form_base"),
            "items": items,
            "items_raw": row.get("items_raw"),
            "accepted_at": row.get("accepted_at"),
            "filing_date": row.get("filing_date"),
            "report_date": row.get("report_date"),
            "usable_trade_date": row.get("usable_trade_date"),
            "pit_safe_flag": row.get("pit_safe_flag"),
            "pit_source": row.get("pit_source"),
            "event_bonus": round(_event_bonus(items), 6),
        }
        by_ticker.setdefault(ticker, []).append(context)
    for rows in by_ticker.values():
        rows.sort(
            key=lambda event: (
                -float(event["event_bonus"]),
                str(event.get("accepted_at") or ""),
                str(event.get("accession_number") or ""),
            )
        )
    return by_ticker


def _event_anchor_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    event_contexts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS or ticker not in event_contexts:
        return None
    base = previous._peer_shock_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
    )
    if base is None:
        return None
    event = event_contexts[ticker][0]
    event_score = float(base["peer_score"]) + float(event["event_bonus"])
    if event_score <= MIN_EVENT_PEER_SCORE:
        return None
    return {
        **base,
        "event_score": round(event_score, 6),
        "event_accession_number": event.get("accession_number"),
        "event_form_type": event.get("form_type"),
        "event_items": event.get("items"),
        "event_items_raw": event.get("items_raw"),
        "event_accepted_at": event.get("accepted_at"),
        "event_filing_date": event.get("filing_date"),
        "event_report_date": event.get("report_date"),
        "event_usable_trade_date": event.get("usable_trade_date"),
        "event_pit_safe_flag": event.get("pit_safe_flag"),
        "event_pit_source": event.get("pit_source"),
        "event_bonus": event.get("event_bonus"),
    }


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
    date_pos = {date_value: idx for idx, date_value in enumerate(all_dates)}
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]

    candidates: list[dict[str, Any]] = []
    event_contexts_out: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_sec_events": 0,
        "days_with_event_anchor_shocks": 0,
        "days_with_laggard_candidates": 0,
        "days_with_corr_pairs": 0,
        "raw_sec_event_tickers": 0,
        "raw_event_anchor_shocks": 0,
        "raw_laggard_candidates": 0,
        "raw_corr_pairs": 0,
        "min_correlation": MIN_CORRELATION,
        "correlation_lookback_days": CORR_LOOKBACK_DAYS,
        "max_event_anchors_per_day": MAX_EVENT_ANCHORS_PER_DAY,
        "max_laggard_candidates_per_day": MAX_LAGGARD_CANDIDATES_PER_DAY,
    }

    eligible_tickers = sorted(
        ticker
        for ticker in sector_entries
        if ticker in snapshot and ticker not in EXCLUDED_TICKERS
    )
    for signal_date in dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < CORR_LOOKBACK_DAYS:
            continue
        event_contexts = _sec_events_by_ticker(signal_date)
        if not event_contexts:
            continue
        scan["days_with_sec_events"] += 1
        scan["raw_sec_event_tickers"] += len(event_contexts)
        prior_dates = all_dates[pos - CORR_LOOKBACK_DAYS : pos]

        anchor_rows = [
            row
            for ticker in sorted(event_contexts)
            if ticker in sector_entries
            and ticker in snapshot
            and (
                row := _event_anchor_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    event_contexts=event_contexts,
                )
            )
            is not None
        ]
        if not anchor_rows:
            continue
        scan["days_with_event_anchor_shocks"] += 1
        scan["raw_event_anchor_shocks"] += len(anchor_rows)
        anchor_rows.sort(
            key=lambda row: (
                -float(row["event_score"]),
                -float(row["peer_signal_day_return"]),
                -float(row["peer_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        anchor_rows = anchor_rows[:MAX_EVENT_ANCHORS_PER_DAY]

        laggard_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := previous._laggard_candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                )
            )
            is not None
            and float(row["candidate_signal_day_return"]) >= MIN_CANDIDATE_SIGNAL_RETURN
            and float(row["candidate_signal_day_return"]) <= MAX_CANDIDATE_SIGNAL_RETURN
        ]
        if not laggard_rows:
            continue
        scan["days_with_laggard_candidates"] += 1
        scan["raw_laggard_candidates"] += len(laggard_rows)
        laggard_rows.sort(
            key=lambda row: (
                -float(row["candidate_lag_quality_score"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        laggard_rows = laggard_rows[:MAX_LAGGARD_CANDIDATES_PER_DAY]

        vector_by_ticker: dict[str, list[float]] = {}
        for row in [*anchor_rows, *laggard_rows]:
            ticker = str(row["ticker"])
            if ticker in vector_by_ticker:
                continue
            vector = previous._prior_return_vector_for_dates(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                prior_dates=prior_dates,
            )
            if vector is not None:
                vector_by_ticker[ticker] = vector

        ab_entries = entries_by_date.get(signal_date, [])
        day_rows: list[dict[str, Any]] = []
        for anchor in anchor_rows:
            anchor_ticker = str(anchor["ticker"])
            anchor_vector = vector_by_ticker.get(anchor_ticker)
            if anchor_vector is None:
                continue
            for laggard in laggard_rows:
                ticker = str(laggard["ticker"])
                if ticker == anchor_ticker:
                    continue
                laggard_vector = vector_by_ticker.get(ticker)
                if laggard_vector is None:
                    continue
                corr = previous._pearson_corr(anchor_vector, laggard_vector)
                if corr is None or corr < MIN_CORRELATION:
                    continue
                same_sector = anchor.get("peer_sector") == laggard.get("sector")
                same_industry = anchor.get("peer_industry") == laggard.get("industry")
                score = (
                    1.90 * corr
                    + 2.25 * float(anchor["peer_relative_vs_spy"])
                    + 1.05 * float(anchor["peer_signal_day_return"])
                    + 0.85 * float(laggard["candidate_lag_quality_score"])
                    + float(anchor["event_bonus"])
                    - 1.05 * max(float(laggard["candidate_signal_day_return"]), 0.0)
                    + (0.06 if same_sector else 0.0)
                    + (0.04 if same_industry else 0.0)
                )
                day_rows.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": "SEC_EVENT_PROVENANCED_PEER_SHOCK_PAPER",
                        "candidate_score": round(score, 6),
                        "anchor_ticker": anchor_ticker,
                        "rolling_corr_60d": round(corr, 6),
                        "same_sector_as_anchor": bool(same_sector),
                        "same_industry_as_anchor": bool(same_industry),
                        "anchor_signal_day_return": anchor["peer_signal_day_return"],
                        "anchor_relative_vs_spy": anchor["peer_relative_vs_spy"],
                        "anchor_volume_ratio_20d": anchor["peer_volume_ratio_20d"],
                        "anchor_ret20_excess_spy": anchor["peer_ret20_excess_spy"],
                        "anchor_avg_dollar_volume_20d": anchor[
                            "peer_avg_dollar_volume_20d"
                        ],
                        "anchor_sector": anchor.get("peer_sector"),
                        "anchor_industry": anchor.get("peer_industry"),
                        "anchor_event_accession_number": anchor[
                            "event_accession_number"
                        ],
                        "anchor_event_form_type": anchor["event_form_type"],
                        "anchor_event_items": anchor["event_items"],
                        "anchor_event_items_raw": anchor["event_items_raw"],
                        "anchor_event_accepted_at": anchor["event_accepted_at"],
                        "anchor_event_filing_date": anchor["event_filing_date"],
                        "anchor_event_report_date": anchor["event_report_date"],
                        "anchor_event_usable_trade_date": anchor[
                            "event_usable_trade_date"
                        ],
                        "anchor_event_pit_safe_flag": anchor[
                            "event_pit_safe_flag"
                        ],
                        "anchor_event_pit_source": anchor["event_pit_source"],
                        "anchor_event_bonus": anchor["event_bonus"],
                        **laggard,
                        "same_day_ab_entry_count": len(ab_entries),
                        "same_day_ab_overlap": bool(ab_entries),
                        "same_ticker_ab_overlap": any(
                            trade.get("ticker") == ticker for trade in ab_entries
                        ),
                        "rule_version": RULE_VERSION,
                        "uses_free_ohlcv": True,
                        "uses_free_sec_events": True,
                        "uses_llm": False,
                        "trade_enabled": False,
                        "known_at": (
                            "SEC usable_trade_date and signal-day OHLCV after "
                            "close before next-open paper entry"
                        ),
                    }
                )

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["rolling_corr_60d"]),
                -float(row["anchor_relative_vs_spy"]),
                -float(row["anchor_event_bonus"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("anchor_ticker") or ""),
                row["ticker"],
            )
        )
        day_rows = day_rows[:MAX_RAW_ROWS_PER_DAY]
        candidates.extend(day_rows)
        scan["days_with_corr_pairs"] += 1
        scan["raw_corr_pairs"] += len(day_rows)
        event_contexts_out.append(
            {
                "date": signal_date,
                "raw_sec_event_ticker_count": len(event_contexts),
                "event_anchor_shock_count": len(anchor_rows),
                "raw_laggard_candidate_count": len(laggard_rows),
                "corr_pair_count_kept": len(day_rows),
                "top_anchor_ticker": day_rows[0]["anchor_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_rolling_corr_60d": day_rows[0]["rolling_corr_60d"],
                "top_anchor_items": day_rows[0]["anchor_event_items"],
                "top_anchor_relative_vs_spy": day_rows[0]["anchor_relative_vs_spy"],
                "top_candidate_signal_day_return": day_rows[0][
                    "candidate_signal_day_return"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["rolling_corr_60d"]),
            -float(row["anchor_relative_vs_spy"]),
            -float(row["anchor_event_bonus"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("anchor_ticker") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "event_form_base_whitelist": sorted(EVENT_FORM_BASE_WHITELIST),
            "event_item_whitelist": sorted(EVENT_ITEM_WHITELIST),
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "accepted_peer_shock_base_min_peer_signal_return": previous.MIN_PEER_SIGNAL_RETURN,
            "accepted_peer_shock_base_min_peer_relative_vs_spy": previous.MIN_PEER_RELATIVE_VS_SPY,
            "accepted_peer_shock_base_min_peer_volume_ratio_20d": previous.MIN_PEER_VOLUME_RATIO_20D,
            "accepted_peer_shock_base_min_candidate_close_location": previous.MIN_CANDIDATE_CLOSE_LOCATION,
            "accepted_peer_shock_base_min_candidate_ret20_excess_spy": previous.MIN_CANDIDATE_RET20_EXCESS_SPY,
            "sec_event_source_dir": _repo_rel(SEC_EVENTS_DIR),
        }
    )
    return candidates, event_contexts_out, scan


def _accepted_peer_shock_comparator() -> dict[str, Any]:
    if not ACCEPTED_PEER_SHOCK_ARTIFACT.exists():
        return {
            "available": False,
            "artifact": _repo_rel(ACCEPTED_PEER_SHOCK_ARTIFACT),
            "reason": "missing_accepted_peer_shock_artifact",
        }
    payload = json.loads(ACCEPTED_PEER_SHOCK_ARTIFACT.read_text(encoding="utf-8"))
    gate = payload.get("gate4", {})
    return {
        "available": True,
        "experiment_id": ACCEPTED_PEER_SHOCK_EXPERIMENT_ID,
        "artifact": _repo_rel(ACCEPTED_PEER_SHOCK_ARTIFACT),
        "decision": payload.get("decision"),
        "expected_value_score_delta_sum": gate.get("aggregate_ev_delta")
        or payload.get("aggregate_expected_value_delta"),
        "total_pnl_delta_sum": gate.get("aggregate_pnl_delta")
        or payload.get("aggregate_strategy_total_pnl_delta"),
        "target_trade_count": gate.get("target_trade_count"),
    }


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
    comparator = _accepted_peer_shock_comparator()
    if comparator.get("available"):
        comparator_ev = comparator.get("expected_value_score_delta_sum")
        comparator_pnl = comparator.get("total_pnl_delta_sum")
        if comparator_ev is not None and aggregate["expected_value_score_delta_sum"] <= float(
            comparator_ev
        ):
            gate["failed_reasons"].append("accepted_peer_shock_ev_not_beaten")
        if comparator_pnl is not None and aggregate["total_pnl_delta_sum"] <= float(
            comparator_pnl
        ):
            gate["failed_reasons"].append("accepted_peer_shock_pnl_not_beaten")
    else:
        gate["failed_reasons"].append("accepted_peer_shock_comparator_missing")
    gate["accepted_peer_shock_comparator"] = comparator
    gate["passed"] = not gate["failed_reasons"]
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_event_provenanced_peer_shock"
        if gate["passed"]
        else "rejected_sec_event_provenanced_peer_shock_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "PIT SEC 8-K event anchors with real price/volume shock should "
                "make rolling-correlated peer shock candidates cleaner than "
                "broad peer matching, because the relation transfer starts "
                "from a dated, replayable company event."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "relation_aware_event_peer_shock",
            "new_evidence_type": "free_PIT_SEC_filing_provenance_plus_OHLCV_relation",
            "nearby_prior_experiments": [
                "exp-20260606-018",
                "exp-20260606-024",
                "exp-20260606-025",
                "exp-20260608-023",
                "exp-20260608-025",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_peer_shock_comparator": payload["gate4"].get(
                "accepted_peer_shock_comparator"
            ),
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that SEC 8-K item "
                "provenance is too sparse or too semantically broad to improve "
                "the already-specific rolling-correlation relation. Do not "
                "answer by sweeping item whitelists, anchor return, volume, "
                "correlation, candidate return, top-N, hold-day, cooldown, or "
                "paper notional thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially stronger relation evidence such as "
                "customer/supplier/product-line links or SEC text extraction "
                "that distinguishes counterparties, contracts, guidance, and "
                "financing events with PIT daily parity."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "event_form_base_whitelist": sorted(EVENT_FORM_BASE_WHITELIST),
            "event_item_whitelist": sorted(EVENT_ITEM_WHITELIST),
            "correlation_lookback_days": CORR_LOOKBACK_DAYS,
            "min_correlation": MIN_CORRELATION,
            "max_event_anchors_per_day": MAX_EVENT_ANCHORS_PER_DAY,
            "max_laggard_candidates_per_day": MAX_LAGGARD_CANDIDATES_PER_DAY,
            "max_raw_rows_per_day": MAX_RAW_ROWS_PER_DAY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: SEC event provenance should improve "
            "rolling-correlation peer-shock transfer by anchoring the shock to "
            "a dated PIT company event instead of generic sector or "
            "characteristic similarity."
        ),
        "2_history_check": {
            "exp-20260606-018/024/025": (
                "Rolling-corr peer shock became an accepted default-off source "
                "when core-flow confirmed it, with comparator +0.3845 EV and "
                "+$6,107.66 PnL. This run must beat that comparator or remain "
                "a rejected scout."
            ),
            "exp-20260608-023": (
                "Sector peer gap reaction transfer failed old_thin and "
                "drawdown because sector is too coarse. This run uses a "
                "ticker-level SEC event anchor plus rolling correlation."
            ),
            "exp-20260608-025": (
                "Same-industry characteristic peer shock did not beat the "
                "accepted comparator. This run changes the evidence source to "
                "PIT SEC event provenance rather than another taxonomy or "
                "characteristic similarity filter."
            ),
            "SEC item experiments": (
                "Prior direct SEC item/phrase retries are frozen without "
                "richer provenance. This run does not buy an SEC item directly; "
                "it uses SEC only as provenance for a confirmed peer shock."
            ),
        },
        "3_single_policy_bundle": (
            "Only one decision hypothesis is tested: SEC-event-provenanced "
            "rolling-correlation peer-shock candidate source. Runner, "
            "comparator, artifact, log, card, ticket, and manifest only "
            "evaluate that fixed replay-only bundle."
        ),
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the accepted "
            "rolling-corr peer-shock comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_027_sec_event_provenanced_peer_shock.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses SEC filing rows with pit_safe_flag=True and "
        "usable_trade_date equal to the signal date, plus close-of-day OHLCV "
        "available on the signal date and 60 prior trading-day returns for "
        "correlation. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["event_contexts_by_window"] = payload.get("pressure_contexts_by_window", {})
    payload["event_context_samples_by_window"] = payload.get(
        "pressure_context_samples_by_window", {}
    )
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The SEC-event-provenanced peer-shock source cleared the strict "
        "three-window replay and beat the accepted rolling-corr peer-shock "
        "comparator, but remains replay-only until a shared default-off "
        "adapter reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The SEC-event-provenanced peer-shock source did not clear Gate 4 "
            "or did not beat the accepted peer-shock comparator; do not "
            "promote or locally retune this SEC-event peer-shock family on "
            "the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "SEC event provenance improves auditability but may still be too "
            "thin and semantically mixed. The accepted rolling-corr peer shock "
            "likely works because relation specificity and core-flow "
            "confirmation are both present; event provenance alone may not "
            "supply the missing capital-flow confirmation."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SEC item whitelist, event bonus, anchor "
            "return, anchor volume, correlation, candidate return, top-N, "
            "hold-day, cooldown, or notional thresholds on these frozen "
            "windows."
        ),
        "new_evidence_required": (
            "Need relation evidence that names actual economic linkage, such "
            "as counterparties, supplier/customer edges, product-line "
            "overlap, or PIT text classification with daily production parity."
        ),
    }
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | SEC days | Anchor days | Corr pairs | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {sec_days} | {anchor_days} | {pairs} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                sec_days=scan.get("days_with_sec_events", 0),
                anchor_days=scan.get("days_with_event_anchor_shocks", 0),
                pairs=scan.get("raw_corr_pairs", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload.get("accepted_peer_shock_comparator") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC-Event-Provenanced Peer Shock",
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
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Comparator EV/PnL: `{}` / `{}`".format(
                comparator.get("expected_value_score_delta_sum"),
                comparator.get("total_pnl_delta_sum"),
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "relation_aware_event_peer_shock",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_peer_shock_comparator": payload.get("accepted_peer_shock_comparator"),
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "sec_event_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_sec_events"
                ),
                "event_anchor_shock_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_event_anchor_shocks"),
                "corr_pair_count": payload["context_scan_by_window"][label].get(
                    "raw_corr_pairs"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


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
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
