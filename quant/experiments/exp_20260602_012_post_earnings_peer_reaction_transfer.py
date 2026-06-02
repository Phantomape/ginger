"""exp-20260602-012: post-earnings peer reaction transfer scout.

This alpha search tests one relation-construction candidate source. A confirmed
positive EPS-surprise issuer must have a positive event-day reaction, then a
liquid same-industry peer can enter a default-off paper sleeve only if that
peer already shows same-day relative strength and trend support.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
shared adapters, and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260602_006_post_earnings_positive_surprise_drift_candidate_pool as parent
from broad_market_sector_map import DEFAULT_CACHE_PATH, load_cache, lookup_sector


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-012"
STEM = "post_earnings_peer_reaction_transfer"
TRIAL_FAMILY = "early_peer_earnings_reaction_transfer"
CHANGED_VARIABLE = "early_peer_earnings_reaction_transfer_candidate_source_v1"
RULE_VERSION = "early_peer_earnings_reaction_transfer_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_012_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

RECENT_SIGNAL_DAYS_MIN = 0
RECENT_SIGNAL_DAYS_MAX = 3
MIN_ISSUER_EVENT_EXCESS_VS_SPY = 0.01
MIN_ISSUER_EVENT_CLOSE_LOCATION = 0.55
MIN_PEER_SIGNAL_EXCESS_VS_SPY = 0.003
MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY = 0.0
MIN_PEER_CLOSE_LOCATION = 0.55
MOVING_AVERAGE_DAYS = parent.MOVING_AVERAGE_DAYS
RELATIVE_STRENGTH_DAYS = parent.RELATIVE_STRENGTH_DAYS
AVG_DOLLAR_VOLUME_DAYS = parent.AVG_DOLLAR_VOLUME_DAYS
MIN_AVG_DOLLAR_VOLUME_20D = parent.MIN_AVG_DOLLAR_VOLUME_20D
MIN_RS20_VS_SPY = parent.MIN_RS20_VS_SPY


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._patch_framework()
    parent.framework._candidate_rows_for_window = _candidate_rows_for_window
    parent.framework._build_report = _build_report


def _norm_industry(value: Any) -> str:
    return str(value or "").strip().lower()


def _industry_peers(
    universe: list[str],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cache = load_cache(DEFAULT_CACHE_PATH)
    lookups: dict[str, dict[str, Any]] = {}
    by_industry: dict[str, list[str]] = defaultdict(list)
    for ticker in sorted(set(universe).intersection(snapshot).difference(parent.framework.EXCLUDED_TICKERS)):
        lookup = lookup_sector(ticker, cache)
        lookups[ticker] = lookup
        if lookup.get("status") != "ok":
            continue
        industry = _norm_industry(lookup.get("industry"))
        if not industry:
            continue
        by_industry[industry].append(ticker)
    coverage = {
        "cache_path": str(DEFAULT_CACHE_PATH.relative_to(REPO_ROOT)),
        "cache_generated_at": cache.get("generated_at"),
        "tickers_with_lookup": len(lookups),
        "ok_lookup_count": sum(1 for row in lookups.values() if row.get("status") == "ok"),
        "industry_count": len(by_industry),
    }
    return lookups, by_industry, coverage


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = parent.framework.ohlcv_helper._baseline_entries(before_result)
    trading_dates = [
        date_value
        for date_value in parent.framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    trading_pos = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    spy_rows = parent.framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = parent.framework.ohlcv_helper._row_index(spy_rows)
    sector_lookup, peers_by_industry, sector_coverage = _industry_peers(universe, snapshot)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    event_count = 0
    issuer_reaction_count = 0
    peer_relation_count = 0
    min_idx = max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS, AVG_DOLLAR_VOLUME_DAYS)

    for event_ticker in sorted(set(universe).intersection(snapshot).difference(parent.framework.EXCLUDED_TICKERS)):
        issuer_lookup = sector_lookup.get(event_ticker) or {}
        issuer_industry = _norm_industry(issuer_lookup.get("industry"))
        if not issuer_industry:
            audit["event_issuer_missing_industry"] += 1
            continue
        peer_tickers = [
            ticker
            for ticker in peers_by_industry.get(issuer_industry, [])
            if ticker != event_ticker
        ]
        if not peer_tickers:
            audit["no_same_industry_peers"] += 1
            continue

        issuer_rows = parent.framework.ohlcv_helper._series(snapshot, event_ticker)
        issuer_idx_by_date = parent.framework.ohlcv_helper._row_index(issuer_rows)
        events = parent._positive_surprise_events(event_ticker, cfg, trading_dates)
        event_count += len(events)
        for event in events:
            event_date = str(event["event_confirmed_date"])
            event_trade_pos = trading_pos.get(event_date)
            issuer_event_idx = issuer_idx_by_date.get(event_date)
            event_spy_idx = spy_index.get(event_date)
            if event_trade_pos is None or issuer_event_idx is None or event_spy_idx is None:
                audit["missing_event_ohlcv"] += 1
                continue
            if issuer_event_idx <= 0 or event_spy_idx <= 0:
                audit["missing_event_prior_close"] += 1
                continue

            issuer_event_return = parent.earnings_helper._close_return(
                issuer_rows,
                issuer_event_idx - 1,
                issuer_event_idx,
            )
            spy_event_return = parent.earnings_helper._close_return(
                spy_rows,
                event_spy_idx - 1,
                event_spy_idx,
            )
            issuer_close_location = parent.framework._close_location(
                issuer_rows[issuer_event_idx]
            )
            if issuer_event_return is None or spy_event_return is None:
                audit["missing_issuer_event_reaction"] += 1
                continue
            issuer_event_excess = issuer_event_return - spy_event_return
            if issuer_event_excess < MIN_ISSUER_EVENT_EXCESS_VS_SPY:
                audit["issuer_event_reaction_too_weak"] += 1
                continue
            if issuer_close_location is None or issuer_close_location < MIN_ISSUER_EVENT_CLOSE_LOCATION:
                audit["issuer_weak_close_location"] += 1
                continue
            issuer_reaction_count += 1

            for offset in range(RECENT_SIGNAL_DAYS_MIN, RECENT_SIGNAL_DAYS_MAX + 1):
                signal_pos = event_trade_pos + offset
                if signal_pos >= len(trading_dates):
                    audit["signal_window_out_of_range"] += 1
                    continue
                signal_date = trading_dates[signal_pos]
                spy_idx = spy_index.get(signal_date)
                if spy_idx is None or spy_idx < RELATIVE_STRENGTH_DAYS:
                    audit["missing_signal_spy_context"] += 1
                    continue
                spy_signal_1d = parent.earnings_helper._close_return(
                    spy_rows,
                    spy_idx - 1,
                    spy_idx,
                )
                spy_event_to_signal_return = parent.earnings_helper._close_return(
                    spy_rows,
                    event_spy_idx - 1,
                    spy_idx,
                )
                if spy_signal_1d is None or spy_event_to_signal_return is None:
                    audit["missing_spy_return_context"] += 1
                    continue

                for peer_ticker in peer_tickers:
                    peer_rows = parent.framework.ohlcv_helper._series(snapshot, peer_ticker)
                    idx_by_date = parent.framework.ohlcv_helper._row_index(peer_rows)
                    event_peer_idx = idx_by_date.get(event_date)
                    idx = idx_by_date.get(signal_date)
                    if event_peer_idx is None or idx is None or idx < min_idx or event_peer_idx <= 0:
                        audit["peer_insufficient_ohlcv_history"] += 1
                        continue
                    close = parent.framework.ohlcv_helper._value(peer_rows[idx], "Close")
                    volume = parent.framework.ohlcv_helper._value(peer_rows[idx], "Volume")
                    if not close or volume is None:
                        audit["peer_missing_close_or_volume"] += 1
                        continue
                    avg_dollar_volume = parent.earnings_helper._avg_dollar_volume(
                        peer_rows,
                        idx,
                        AVG_DOLLAR_VOLUME_DAYS,
                    )
                    if avg_dollar_volume is None:
                        audit["peer_missing_avg_dollar_volume"] += 1
                        continue
                    if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                        audit["peer_low_avg_dollar_volume"] += 1
                        continue

                    ma50 = parent.earnings_helper._prior_average(
                        peer_rows,
                        idx,
                        MOVING_AVERAGE_DAYS,
                        "Close",
                    )
                    if ma50 is None or float(close) <= ma50:
                        audit["peer_below_50d_trend"] += 1
                        continue
                    close_location = parent.framework._close_location(peer_rows[idx])
                    if close_location is None or close_location < MIN_PEER_CLOSE_LOCATION:
                        audit["peer_weak_close_location"] += 1
                        continue

                    ret20 = parent.earnings_helper._close_return(
                        peer_rows,
                        idx - RELATIVE_STRENGTH_DAYS,
                        idx,
                    )
                    spy_ret20 = parent.earnings_helper._close_return(
                        spy_rows,
                        spy_idx - RELATIVE_STRENGTH_DAYS,
                        spy_idx,
                    )
                    if ret20 is None or spy_ret20 is None:
                        audit["peer_missing_relative_strength"] += 1
                        continue
                    rs20_vs_spy = ret20 - spy_ret20
                    if rs20_vs_spy <= MIN_RS20_VS_SPY:
                        audit["peer_rs20_not_positive_vs_spy"] += 1
                        continue

                    peer_signal_return_1d = parent.earnings_helper._close_return(
                        peer_rows,
                        idx - 1,
                        idx,
                    )
                    if peer_signal_return_1d is None:
                        audit["peer_missing_signal_return"] += 1
                        continue
                    peer_signal_excess = peer_signal_return_1d - spy_signal_1d
                    if peer_signal_excess < MIN_PEER_SIGNAL_EXCESS_VS_SPY:
                        audit["peer_signal_day_too_weak"] += 1
                        continue

                    peer_event_to_signal_return = parent.earnings_helper._close_return(
                        peer_rows,
                        event_peer_idx - 1,
                        idx,
                    )
                    if peer_event_to_signal_return is None:
                        audit["peer_missing_event_to_signal_return"] += 1
                        continue
                    peer_event_to_signal_excess = (
                        peer_event_to_signal_return - spy_event_to_signal_return
                    )
                    if peer_event_to_signal_excess < MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY:
                        audit["peer_event_to_signal_excess_too_weak"] += 1
                        continue

                    ab_entries = entries_by_date.get(signal_date, [])
                    peer_lookup = sector_lookup.get(peer_ticker) or {}
                    score = (
                        issuer_event_excess
                        + peer_signal_excess
                        + peer_event_to_signal_excess
                        + rs20_vs_spy
                        + (float(event["latest_surprise_pct"]) / 100.0)
                        + (close_location / 10.0)
                    )
                    candidates.append(
                        {
                            "ticker": peer_ticker,
                            "date": signal_date,
                            "strategy": STEM,
                            "rule_version": RULE_VERSION,
                            "close": parent.framework.base._round(close, 4),
                            "volume": parent.framework.base._round(volume, 2),
                            "avg_dollar_volume_20d": parent.framework.base._round(
                                avg_dollar_volume,
                                2,
                            ),
                            "ma50": parent.framework.base._round(ma50, 4),
                            "close_location": parent.framework.base._round(
                                close_location,
                                6,
                            ),
                            "ret20": parent.framework.base._round(ret20, 6),
                            "spy_ret20": parent.framework.base._round(spy_ret20, 6),
                            "rs20_vs_spy": parent.framework.base._round(rs20_vs_spy, 6),
                            "peer_signal_return_1d": parent.framework.base._round(
                                peer_signal_return_1d,
                                6,
                            ),
                            "peer_signal_excess_return_1d_vs_spy": (
                                parent.framework.base._round(peer_signal_excess, 6)
                            ),
                            "peer_event_to_signal_return": parent.framework.base._round(
                                peer_event_to_signal_return,
                                6,
                            ),
                            "peer_event_to_signal_excess_vs_spy": (
                                parent.framework.base._round(
                                    peer_event_to_signal_excess,
                                    6,
                                )
                            ),
                            "event_ticker": event_ticker,
                            "event_confirmed_date": event_date,
                            "event_industry": issuer_lookup.get("industry"),
                            "event_sector": issuer_lookup.get("sector"),
                            "event_issuer_return_1d": parent.framework.base._round(
                                issuer_event_return,
                                6,
                            ),
                            "event_issuer_excess_return_1d_vs_spy": (
                                parent.framework.base._round(issuer_event_excess, 6)
                            ),
                            "event_issuer_close_location": parent.framework.base._round(
                                issuer_close_location,
                                6,
                            ),
                            "peer_industry": peer_lookup.get("industry"),
                            "peer_sector": peer_lookup.get("sector"),
                            "peer_relation_source": "exact_yfinance_industry_match",
                            "peer_relation_key": issuer_industry,
                            "recent_signal_trading_day_offset": offset,
                            "latest_surprise_pct": parent.framework.base._round(
                                event["latest_surprise_pct"],
                                6,
                            ),
                            "avg_historical_surprise_pct": parent.framework.base._round(
                                event["avg_historical_surprise_pct"],
                                6,
                            ),
                            "historical_surprise_count": event["historical_surprise_count"],
                            "positive_historical_surprise_count": event[
                                "positive_historical_surprise_count"
                            ],
                            "eps_actual_last": parent.framework.base._round(
                                event["eps_actual_last"],
                                6,
                            ),
                            "earnings_snapshot_source_date": event[
                                "earnings_snapshot_source_date"
                            ],
                            "previous_snapshot_source_date": event[
                                "previous_snapshot_source_date"
                            ],
                            "peer_transfer_score": parent.framework.base._round(score, 6),
                            "same_day_ab_entry_count": len(ab_entries),
                            "same_day_ab_overlap": bool(ab_entries),
                            "same_ticker_ab_overlap": any(
                                trade.get("ticker") == peer_ticker for trade in ab_entries
                            ),
                            "known_at": "after_peer_signal_date_close_before_next_open_paper_entry",
                            "trade_enabled": False,
                            "alters_orders": False,
                        }
                    )
                    peer_relation_count += 1

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["peer_transfer_score"]),
            int(row["recent_signal_trading_day_offset"]),
            -float(row["event_issuer_excess_return_1d_vs_spy"]),
            -float(row["peer_signal_excess_return_1d_vs_spy"]),
            -float(row["peer_event_to_signal_excess_vs_spy"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(trading_dates),
        "positive_surprise_event_count": event_count,
        "issuer_positive_reaction_event_count": issuer_reaction_count,
        "peer_relation_candidate_count": peer_relation_count,
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "unique_event_tickers": len({row["event_ticker"] for row in candidates}),
        "sector_map_source": "data/reference/broad_market_sector_map.json",
        "sector_map_coverage": sector_coverage,
        "relation_field": "exact yfinance industry string match",
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "earnings_snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter_and_forward_rows"
        if gate4["passed"]
        else "rejected_post_earnings_peer_reaction_transfer"
    )
    actual_success = 1 if gate4["passed"] else 0
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    prediction = {
        "success_probability": 0.22,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "peer_transfer_window_regression",
            "thin_sample",
            "concentration_failed",
            "drawdown_drift",
        ],
        "confidence_reason": (
            "Playbook points to early peer earnings transfer as a stronger relation "
            "source, but local peer-transfer and post-earnings candidate-pool "
            "experiments have failed recently, so prior success probability is low."
        ),
        "recorded_at": "2026-06-02T08:06:24+00:00",
        "brier_score": round((0.22 - actual_success) ** 2, 6),
    }
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Confirmed positive EPS-surprise reactions may transfer to liquid "
                "same-industry peers that already show same-day RS, creating a "
                "default-off paper candidate source distinct from issuer-only PEAD."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "event_graph_relation_candidate_pool",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260530-023",
                "exp-20260531-010",
                "exp-20260602-006",
                "exp-20260602-011",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "production_visible_earnings_snapshot_peer_relation_field",
            "prediction": prediction,
            "calibration": {
                "actual_decision": decision,
                "actual_success": actual_success,
                "predicted_success_probability": prediction["success_probability"],
                "brier_score": prediction["brier_score"],
                "expected_ev_delta": prediction["expected_ev_delta"],
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "expected_pnl_delta": prediction["expected_pnl_delta"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
                "predicted_failure_modes": prediction["main_failure_modes"],
                "realized_failure_mode": None
                if gate4["passed"]
                else "; ".join(gate4["failed_reasons"]),
                "predicted_failure_mode_hit": (
                    False
                    if gate4["passed"]
                    else any(
                        token in "; ".join(gate4["failed_reasons"])
                        for token in ["window", "sample", "concentration", "drawdown"]
                    )
                ),
            },
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "paper_notional_usd": parent.framework.base.BASE_NOTIONAL_USD,
                "hold_days": parent.framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": parent.framework.MAX_PAPER_TRADES_PER_DAY,
                "recent_signal_days_min": RECENT_SIGNAL_DAYS_MIN,
                "recent_signal_days_max": RECENT_SIGNAL_DAYS_MAX,
                "min_issuer_event_excess_vs_spy": MIN_ISSUER_EVENT_EXCESS_VS_SPY,
                "min_issuer_event_close_location": MIN_ISSUER_EVENT_CLOSE_LOCATION,
                "min_peer_signal_excess_vs_spy": MIN_PEER_SIGNAL_EXCESS_VS_SPY,
                "min_peer_event_to_signal_excess_vs_spy": (
                    MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY
                ),
                "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "locked_parent_positive_surprise_variables": {
                    "min_latest_surprise_pct": parent.MIN_LATEST_SURPRISE_PCT,
                    "min_positive_surprise_count": parent.MIN_POSITIVE_SURPRISE_COUNT,
                    "min_surprise_history_count": parent.MIN_SURPRISE_HISTORY_COUNT,
                    "min_reset_dte": parent.MIN_RESET_DTE,
                    "max_pre_reset_dte": parent.MAX_PRE_RESET_DTE,
                },
                "source_definition": [
                    "event issuer has PIT earnings snapshot transition-confirmed positive EPS surprise",
                    "issuer event-day return beats SPY by at least 1pp and closes in upper 55% of range",
                    "candidate is a different ticker with exact yfinance industry match",
                    "candidate has signal-day return beating SPY by at least 0.3pp",
                    "candidate event-to-signal return beats SPY and has positive 20d RS",
                    "candidate is liquid, above prior 50d average, and close_location >= 0.55",
                    "top-1 selected paper entry per signal date",
                ],
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: positive earnings-surprise reactions "
                    "may transfer to same-industry peers when the peer is already "
                    "confirming with same-day RS."
                ),
                "2_history_check": {
                    "exp-20260530-023": (
                        "SEC Item 2.02 exact-industry peer transfer failed aggregate "
                        "EV/PnL and sample/concentration gates."
                    ),
                    "exp-20260531-010": (
                        "Characteristic-similarity peer transfer failed; this run "
                        "uses confirmed EPS surprise plus price reaction, not only "
                        "static peer similarity."
                    ),
                    "exp-20260602-006": (
                        "Issuer-only positive-surprise drift improved aggregate but "
                        "failed one window and drawdown."
                    ),
                    "exp-20260602-011": (
                        "Issuer underreaction close-location cap was positive but "
                        "failed sample gate."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; "
                    ">=20 paper trades across all 3 windows; drawdown drift <=0.5pp; "
                    "survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_012_post_earnings_peer_reaction_transfer.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe event joins remain "
                "sparse. Skipped Companyfacts, VBB, FINRA, consensus, Space, and "
                "state-surface retunes because current playbook requires forward "
                "rows or materially new fields. This tests a distinct relation "
                "construction field suggested by the event-graph queue."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. A future promotion would "
                    "need the exact relation field moved into a shared default-off "
                    "adapter using the same earnings snapshot and sector-map inputs "
                    "available to production before next-open paper entry."
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "live_orders_changed": False,
            },
            "interpretation": (
                "The early peer earnings-reaction transfer source cleared Gate 4 "
                "as a replay lead, but no shared adapter was promoted."
                if gate4["passed"]
                else (
                    "The early peer earnings-reaction transfer source did not clear "
                    "Gate 4. Do not promote it or retry nearby peer-transfer "
                    "relation thresholds on these frozen windows without forward "
                    "rows or a stronger relation source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a stronger peer relation source "
                "such as audited customer/supplier links, source overlap, or "
                "multi-season early-peer earnings transfer evidence."
            ),
            "related_files": [
                "quant/experiments/exp_20260602_012_post_earnings_peer_reaction_transfer.py",
                "data/experiments/exp-20260602-012/exp_20260602_012_post_earnings_peer_reaction_transfer.json",
                "data/experiments/exp-20260602-012/post_earnings_peer_reaction_transfer_before_aggregate.json",
                "data/experiments/exp-20260602-012/post_earnings_peer_reaction_transfer_after_aggregate.json",
                "experiments/logs/exp-20260602-012.json",
                "experiments/tickets/exp-20260602-012.json",
                "experiments/artifacts/exp-20260602-012_post_earnings_peer_reaction_transfer.md",
                "docs/experiment_log.jsonl",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Issuer event confirmation is derived from canonical daily earnings "
        "snapshot transitions. Issuer and peer OHLCV are observed through the "
        "peer signal-date close; paper entry is next open and exit is ten trading "
        "days after signal."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "earnings_snapshots": {
            "source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "snapshots_loaded": parent.earnings_helper._EARNINGS_DATE_COUNT,
            "required_fields": [
                "days_to_earnings",
                "eps_actual_last",
                "historical_surprise_pct",
                "avg_historical_surprise_pct",
            ],
            "tickers_with_snapshot_rows": len(parent.earnings_helper._load_earnings_index()),
        },
        "peer_relation": {
            "source": "data/reference/broad_market_sector_map.json",
            "required_fields": ["sector", "industry", "status"],
            "relation": "exact yfinance industry string match",
        },
        "ohlcv": {
            "required_fields": [
                "issuer event-day OHLCV",
                "peer signal-day OHLCV",
                "SPY event and signal-day OHLCV",
            ],
            "decision_time": "known after peer signal-day close before next-open paper entry",
        },
    }
    payload["gate2"]["target_trade_field_coverage"] = parent.framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "event_ticker",
            "event_confirmed_date",
            "event_industry",
            "peer_industry",
            "latest_surprise_pct",
            "eps_actual_last",
            "event_issuer_excess_return_1d_vs_spy",
            "peer_signal_excess_return_1d_vs_spy",
            "peer_event_to_signal_excess_vs_spy",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Issuer reactions | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in parent.framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {events} | {reactions} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                events=audit.get("positive_surprise_event_count", 0),
                reactions=audit.get("issuer_positive_reaction_event_count", 0),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260602-012 Post-Earnings Peer Reaction Transfer",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: exact-industry peer-transfer candidate source after a confirmed positive EPS-surprise issuer reaction.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    base = parent.framework.base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Post-earnings peer reaction transfer",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": base._repo_rel(ARTIFACT_MD),
        "json": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._write_text(CARD_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = parent.framework.base
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
        "card": base._repo_rel(CARD_MD),
        "artifact": base._repo_rel(ARTIFACT_MD),
        "manifest": base._repo_rel(MANIFEST_JSON),
        "experiment_log": base._repo_rel(EXPERIMENT_LOG),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(parent.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            parent.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": parent.framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": parent.framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": parent.framework.base._repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
