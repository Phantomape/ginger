"""exp-20260608-028: negative peer-shock resilient substitute candidates.

Replay-only alpha search. This tests one production-visible free-OHLCV relation:
when a highly correlated liquid peer has a negative shock, a substitute stock
that holds up on the same signal day and has same-day core A/B flow may receive
replacement capital over the next 10 trading days.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260606_018_rolling_corr_peer_shock_lag_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-028"
STEM = "negative_peer_shock_resilience"
TRIAL_FAMILY = "negative_peer_shock_resilient_substitute_candidate_pool"
TRIAL_VARIANT_ID = "negative_peer_shock_resilient_substitute_top1_next_open_10d_v1"
CHANGED_VARIABLE = "negative_peer_shock_resilient_substitute_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_028_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

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

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
CORR_LOOKBACK_DAYS = previous.CORR_LOOKBACK_DAYS
MIN_CORRELATION = previous.MIN_CORRELATION
MAX_SHOCK_PEERS_PER_DAY = 10
MAX_RESILIENT_CANDIDATES_PER_DAY = 350
MAX_RAW_ROWS_PER_DAY = 50

MAX_PEER_SIGNAL_RETURN = -0.045
MAX_PEER_RELATIVE_VS_SPY = -0.035
MIN_PEER_VOLUME_RATIO_20D = 1.10
MAX_PEER_CLOSE_LOCATION = 0.45
MIN_PEER_RET20_EXCESS_SPY = -0.08

MIN_CANDIDATE_SIGNAL_RETURN = -0.005
MAX_CANDIDATE_SIGNAL_RETURN = 0.025
MIN_CANDIDATE_CLOSE_LOCATION = 0.55
MIN_CANDIDATE_RET5 = -0.040
MAX_CANDIDATE_RET5 = 0.070
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.030
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.070
MAX_CANDIDATE_REALIZED_VOL_20D = 0.085

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "old_thin_regression",
        "drawdown_drift",
        "negative_peer_shock_is_bad_news_contagion",
        "not_incremental_vs_accepted_peer_shock",
        "target_sample_too_small",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted rolling-correlation peer shock validates specific relation "
        "edges, but stress/resilience and SEC/sector peer neighbors recently "
        "failed. This is a distinct negative-shock substitution mechanism with "
        "low prior odds."
    ),
    "recorded_at": "2026-06-09T00:07:30+00:00",
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
        "same negative peer-shock fields, trailing 60-day correlation, "
        "candidate resilience gates, same-day core-flow requirement, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, comparator, and concentration "
        "controls in both historical replay and daily production."
    ),
}

BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_GATE4 = previous.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _negative_peer_shock_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < CORR_LOOKBACK_DAYS + 1 or spy_idx < 20:
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    volume_ratio = framework._volume_ratio(rows, idx)
    close_location = framework._close_location(rows[idx])
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if (
        signal_return is None
        or spy_return is None
        or volume_ratio is None
        or close_location is None
        or ret20 is None
        or spy_ret20 is None
    ):
        return None
    relative_vs_spy = signal_return - spy_return
    ret20_excess_spy = ret20 - spy_ret20
    if signal_return > MAX_PEER_SIGNAL_RETURN:
        return None
    if relative_vs_spy > MAX_PEER_RELATIVE_VS_SPY:
        return None
    if volume_ratio < MIN_PEER_VOLUME_RATIO_20D:
        return None
    if close_location > MAX_PEER_CLOSE_LOCATION:
        return None
    if ret20_excess_spy < MIN_PEER_RET20_EXCESS_SPY:
        return None
    shock_score = (
        2.50 * abs(signal_return)
        + 2.00 * abs(relative_vs_spy)
        + 0.20 * min(volume_ratio, 5.0)
        + 0.35 * (1.0 - close_location)
        + 0.05 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    sector_meta = sector_entries[ticker]
    return {
        "ticker": ticker,
        "peer_signal_day_return": round(signal_return, 6),
        "peer_relative_vs_spy": round(relative_vs_spy, 6),
        "peer_volume_ratio_20d": round(volume_ratio, 6),
        "peer_close_location": round(close_location, 6),
        "peer_ret20_excess_spy": round(ret20_excess_spy, 6),
        "peer_avg_dollar_volume_20d": round(adv20, 2),
        "peer_negative_shock_score": round(shock_score, 6),
        "peer_score": round(shock_score, 6),
        "peer_sector": sector_meta.get("sector"),
        "peer_industry": sector_meta.get("industry"),
    }


def _resilient_candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < CORR_LOOKBACK_DAYS + 1 or spy_idx < 60 or idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    required = [
        signal_return,
        close_location,
        ret5,
        ret20,
        ret60,
        spy_return,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_return is not None
    assert close_location is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_return is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    signal_excess_spy = signal_return - spy_return
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if signal_return > MAX_CANDIDATE_SIGNAL_RETURN:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if ret5 < MIN_CANDIDATE_RET5 or ret5 > MAX_CANDIDATE_RET5:
        return None
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if realized_vol20 > MAX_CANDIDATE_REALIZED_VOL_20D:
        return None
    sector_meta = sector_entries[ticker]
    resilience_quality = (
        1.15 * signal_excess_spy
        + 0.70 * signal_return
        + 0.65 * close_location
        + 0.45 * ret20_excess_spy
        + 0.20 * ret60_excess_spy
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.30 * realized_vol20
        - 0.05 * max(volume_ratio - 3.0, 0.0)
    )
    return {
        "ticker": ticker,
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_signal_excess_spy": round(signal_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "candidate_lag_quality_score": round(resilience_quality, 6),
        "candidate_resilience_quality_score": round(resilience_quality, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
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
    peer_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_negative_peer_shocks": 0,
        "days_with_resilient_candidates": 0,
        "days_with_core_flow": 0,
        "days_with_corr_pairs": 0,
        "raw_negative_peer_shocks": 0,
        "raw_resilient_candidates": 0,
        "raw_corr_pairs": 0,
        "min_correlation": MIN_CORRELATION,
        "correlation_lookback_days": CORR_LOOKBACK_DAYS,
        "max_shock_peers_per_day": MAX_SHOCK_PEERS_PER_DAY,
        "max_resilient_candidates_per_day": MAX_RESILIENT_CANDIDATES_PER_DAY,
    }

    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in snapshot)
    for signal_date in dates:
        ab_entries = entries_by_date.get(signal_date, [])
        if not ab_entries:
            continue
        scan["days_with_core_flow"] += 1
        pos = date_pos.get(signal_date)
        if pos is None or pos < CORR_LOOKBACK_DAYS:
            continue
        prior_dates = all_dates[pos - CORR_LOOKBACK_DAYS : pos]

        peer_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _negative_peer_shock_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                )
            )
            is not None
        ]
        if not peer_rows:
            continue
        scan["days_with_negative_peer_shocks"] += 1
        scan["raw_negative_peer_shocks"] += len(peer_rows)
        peer_rows.sort(
            key=lambda row: (
                -float(row["peer_negative_shock_score"]),
                float(row["peer_signal_day_return"]),
                -float(row["peer_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        peer_rows = peer_rows[:MAX_SHOCK_PEERS_PER_DAY]

        resilient_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _resilient_candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                )
            )
            is not None
        ]
        if not resilient_rows:
            continue
        scan["days_with_resilient_candidates"] += 1
        scan["raw_resilient_candidates"] += len(resilient_rows)
        resilient_rows.sort(
            key=lambda row: (
                -float(row["candidate_resilience_quality_score"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        resilient_rows = resilient_rows[:MAX_RESILIENT_CANDIDATES_PER_DAY]

        vector_by_ticker: dict[str, list[float]] = {}
        for row in [*peer_rows, *resilient_rows]:
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

        day_rows: list[dict[str, Any]] = []
        for peer in peer_rows:
            peer_ticker = str(peer["ticker"])
            peer_vector = vector_by_ticker.get(peer_ticker)
            if peer_vector is None:
                continue
            for candidate in resilient_rows:
                ticker = str(candidate["ticker"])
                if ticker == peer_ticker:
                    continue
                candidate_vector = vector_by_ticker.get(ticker)
                if candidate_vector is None:
                    continue
                corr = previous._pearson_corr(peer_vector, candidate_vector)
                if corr is None or corr < MIN_CORRELATION:
                    continue
                same_sector = peer.get("peer_sector") == candidate.get("sector")
                same_industry = peer.get("peer_industry") == candidate.get("industry")
                score = (
                    1.70 * corr
                    + 1.20 * float(peer["peer_negative_shock_score"])
                    + 1.10 * float(candidate["candidate_resilience_quality_score"])
                    + 0.80 * float(candidate["candidate_signal_excess_spy"])
                    + 0.25 * float(candidate["candidate_close_location"])
                    + (0.08 if same_sector else 0.0)
                    + (0.05 if same_industry else 0.0)
                )
                day_rows.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": "NEGATIVE_PEER_SHOCK_RESILIENCE_PAPER",
                        "candidate_score": round(score, 6),
                        "peer_ticker": peer_ticker,
                        "rolling_corr_60d": round(corr, 6),
                        "same_sector_as_peer": bool(same_sector),
                        "same_industry_as_peer": bool(same_industry),
                        "peer_signal_day_return": peer["peer_signal_day_return"],
                        "peer_relative_vs_spy": peer["peer_relative_vs_spy"],
                        "peer_volume_ratio_20d": peer["peer_volume_ratio_20d"],
                        "peer_close_location": peer["peer_close_location"],
                        "peer_ret20_excess_spy": peer["peer_ret20_excess_spy"],
                        "peer_avg_dollar_volume_20d": peer[
                            "peer_avg_dollar_volume_20d"
                        ],
                        "peer_negative_shock_score": peer["peer_negative_shock_score"],
                        "peer_sector": peer.get("peer_sector"),
                        "peer_industry": peer.get("peer_industry"),
                        **candidate,
                        "same_day_ab_entry_count": len(ab_entries),
                        "same_day_ab_overlap": True,
                        "same_ticker_ab_overlap": any(
                            trade.get("ticker") == ticker for trade in ab_entries
                        ),
                        "rule_version": RULE_VERSION,
                        "uses_free_ohlcv_only": True,
                        "uses_llm": False,
                        "trade_enabled": False,
                        "known_at": (
                            "after_signal_day_close_before_next_open_paper_entry"
                        ),
                    }
                )

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["rolling_corr_60d"]),
                -float(row["candidate_resilience_quality_score"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("peer_ticker") or ""),
                row["ticker"],
            )
        )
        day_rows = day_rows[:MAX_RAW_ROWS_PER_DAY]
        candidates.extend(day_rows)
        scan["days_with_corr_pairs"] += 1
        scan["raw_corr_pairs"] += len(day_rows)
        peer_contexts.extend(
            {
                "date": signal_date,
                "peer_ticker": row.get("peer_ticker"),
                "ticker": row.get("ticker"),
                "rolling_corr_60d": row.get("rolling_corr_60d"),
                "peer_signal_day_return": row.get("peer_signal_day_return"),
                "candidate_signal_day_return": row.get(
                    "candidate_signal_day_return"
                ),
                "same_day_ab_entry_count": len(ab_entries),
            }
            for row in day_rows[:10]
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["rolling_corr_60d"]),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "max_peer_signal_return": MAX_PEER_SIGNAL_RETURN,
            "max_peer_relative_vs_spy": MAX_PEER_RELATIVE_VS_SPY,
            "min_peer_volume_ratio_20d": MIN_PEER_VOLUME_RATIO_20D,
            "max_peer_close_location": MAX_PEER_CLOSE_LOCATION,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        }
    )
    return candidates, peer_contexts, scan


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
        "positive_replay_lead_not_promoted_negative_peer_shock_resilience"
        if gate["passed"]
        else "rejected_negative_peer_shock_resilience_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Negative high-correlation peer shocks may identify resilient "
                "substitute stocks when the candidate holds up on the signal "
                "day and same-day core A/B flow confirms market demand."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": (
                "production_visible_negative_peer_shock_relation_with_core_flow"
            ),
            "nearby_prior_experiments": [
                "exp-20260606-018",
                "exp-20260606-024",
                "exp-20260606-025",
                "exp-20260607-023",
                "exp-20260608-023",
                "exp-20260608-025",
                "exp-20260608-027",
            ],
            "prior_trial_count": 6,
            "multiple_testing_risk_bucket": "moderate",
            "accepted_peer_shock_comparator": payload["gate4"].get(
                "accepted_peer_shock_comparator"
            ),
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that a negative peer shock "
                "still transmits bad information to correlated stocks, or that "
                "same-day resilience is already captured by the accepted core "
                "flow and does not beat the accepted positive peer-shock "
                "comparator. Do not answer by sweeping shock, correlation, "
                "resilience, top-N, hold-day, cooldown, or notional thresholds "
                "on these frozen windows."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. Live "
                "activation would require closed forward replacement-value "
                "rows and a separate Gate 1-4 execution-envelope test."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "core_flow_confirmation_required": True,
            "min_correlation": MIN_CORRELATION,
            "max_peer_signal_return": MAX_PEER_SIGNAL_RETURN,
            "max_peer_relative_vs_spy": MAX_PEER_RELATIVE_VS_SPY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: negative high-correlation peer shocks may "
            "cause capital to rotate into resilient substitutes when same-day "
            "core flow confirms market demand."
        ),
        "2_history_check": {
            "exp-20260606-018": (
                "Positive rolling-correlation peer shock improved aggregate "
                "but failed old_thin and drawdown before core-flow filtering."
            ),
            "exp-20260606-024/025": (
                "Core-flow confirmed positive peer shock became an accepted "
                "default-off relation comparator. This run must record and "
                "beat that comparator before any promotion."
            ),
            "exp-20260607-023 and exp-20260608-023/025/027": (
                "Stress leadership, sector peer, same-industry characteristic, "
                "and SEC-event peer variants failed. This run tests a fixed "
                "negative-shock substitution mechanism, not a threshold sweep."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the accepted rolling-corr "
            "peer-shock comparator is beaten. Positive replay remains a lead "
            "until shared adapter parity exists."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_028_negative_peer_shock_resilience.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted"
        if payload["gate4"]["passed"]
        else "rejected"
    )
    payload["interpretation"] = (
        "The negative peer-shock resilience source cleared the strict "
        "three-window replay and beat the accepted rolling-corr peer-shock "
        "comparator, but remains replay-only until a shared default-off "
        "adapter reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The negative peer-shock resilience source did not clear Gate 4 "
            "or did not beat the accepted peer-shock comparator; do not "
            "promote or locally retune this negative peer-shock family on "
            "the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "A negative peer shock may be interpreted as contagion across "
            "correlated stocks rather than as rotation into substitutes. If "
            "the source is positive versus core but fails the accepted peer "
            "comparator, the edge is not strong enough to displace the existing "
            "relation sleeve."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping negative peer shock return, SPY-relative "
            "shock, peer volume, candidate resilience, correlation, same-day "
            "core-flow, top-N, hold-day, cooldown, or notional thresholds on "
            "these frozen windows."
        ),
        "new_evidence_required": (
            "Need a materially new PIT relation source that distinguishes "
            "substitution from contagion, such as customer/supplier/product "
            "links, source-family event transfer, or closed forward rows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Core-flow days | Shock days | Corr pairs | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {core_days} | {shock_days} | {pairs} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                core_days=scan.get("days_with_core_flow", 0),
                shock_days=scan.get("days_with_negative_peer_shocks", 0),
                pairs=scan.get("raw_corr_pairs", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload.get("accepted_peer_shock_comparator") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Negative Peer-Shock Resilience",
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
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
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
                "negative_peer_shock_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_negative_peer_shocks"),
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
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
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
