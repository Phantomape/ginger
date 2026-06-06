"""exp-20260606-018: rolling-correlation peer shock lag candidate pool.

Replay-only alpha search. This tests one production-visible free-OHLCV
relation source: when a liquid peer has an event-like positive daily shock,
stocks with high trailing return correlation that have not yet moved become
top-1 next-open default-off paper candidates with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260606-018"
STEM = "rolling_corr_peer_shock_lag_candidate_pool"
TRIAL_FAMILY = "rolling_corr_peer_shock_lag_candidate_pool"
TRIAL_VARIANT_ID = "rolling_corr_peer_shock_lag_top1_next_open_10d_v1"
CHANGED_VARIABLE = "rolling_corr_peer_shock_lag_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
CORR_LOOKBACK_DAYS = 60
MIN_CORRELATION = 0.58
MAX_SHOCK_PEERS_PER_DAY = 10
MAX_LAGGARD_CANDIDATES_PER_DAY = 350
MAX_RAW_ROWS_PER_DAY = 50

MIN_PEER_SIGNAL_RETURN = 0.055
MIN_PEER_RELATIVE_VS_SPY = 0.040
MIN_PEER_VOLUME_RATIO_20D = 1.05
MIN_PEER_RET20_EXCESS_SPY = -0.02

MIN_CANDIDATE_SIGNAL_RETURN = -0.025
MAX_CANDIDATE_SIGNAL_RETURN = 0.020
MIN_CANDIDATE_CLOSE_LOCATION = 0.35
MIN_CANDIDATE_RET5 = -0.055
MAX_CANDIDATE_RET5 = 0.055
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.030
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.080
MAX_CANDIDATE_REALIZED_VOL_20D = 0.090

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "correlation_instability",
        "own_momentum_relabeling",
        "target_sample_too_small",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Meta research favors production-visible default-off candidate-pool "
        "adapters, but many broad OHLCV and taxonomy-peer variants failed. "
        "Rolling trailing-correlation peer shock is a materially new "
        "free-data relation field rather than a same-industry peer or own "
        "5-day momentum retune."
    ),
    "recorded_at": "2026-06-06T16:07:41Z",
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
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same sector-"
        "known liquid warehouse universe, peer-shock fields, trailing 60-day "
        "correlation known before signal close, laggard candidate fields, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, and concentration controls in "
        "both replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface could "
        "change."
    ),
}

BASE_GATE4 = framework._gate4
BASE_BUILD_PAYLOAD = framework._build_payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _prior_return_vector_for_dates(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    prior_dates: list[str],
) -> list[float] | None:
    rows = snapshot.get(ticker) or []
    ticker_indices = indices.get(ticker, {})
    values: list[float] = []
    for day in prior_dates:
        idx = ticker_indices.get(day)
        if idx is None or idx < 1:
            return None
        ret = framework._daily_return(rows, idx)
        if ret is None:
            return None
        values.append(float(ret))
    return values


def _pearson_corr(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < CORR_LOOKBACK_DAYS:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_demeaned = [value - left_mean for value in left]
    right_demeaned = [value - right_mean for value in right]
    left_var = sum(value * value for value in left_demeaned)
    right_var = sum(value * value for value in right_demeaned)
    if left_var <= 0.0 or right_var <= 0.0:
        return None
    cov = sum(a * b for a, b in zip(left_demeaned, right_demeaned))
    return cov / math.sqrt(left_var * right_var)


def _peer_shock_for_ticker(
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
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if (
        signal_return is None
        or spy_return is None
        or volume_ratio is None
        or ret20 is None
        or spy_ret20 is None
    ):
        return None
    relative_vs_spy = signal_return - spy_return
    ret20_excess_spy = ret20 - spy_ret20
    if signal_return < MIN_PEER_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_PEER_RELATIVE_VS_SPY:
        return None
    if volume_ratio < MIN_PEER_VOLUME_RATIO_20D:
        return None
    if ret20_excess_spy < MIN_PEER_RET20_EXCESS_SPY:
        return None
    sector_meta = sector_entries[ticker]
    score = (
        3.0 * signal_return
        + 2.0 * relative_vs_spy
        + 0.30 * ret20_excess_spy
        + 0.08 * min(volume_ratio, 5.0)
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "ticker": ticker,
        "peer_signal_day_return": round(signal_return, 6),
        "peer_relative_vs_spy": round(relative_vs_spy, 6),
        "peer_volume_ratio_20d": round(volume_ratio, 6),
        "peer_ret20_excess_spy": round(ret20_excess_spy, 6),
        "peer_avg_dollar_volume_20d": round(adv20, 2),
        "peer_score": round(score, 6),
        "peer_sector": sector_meta.get("sector"),
        "peer_industry": sector_meta.get("industry"),
    }


def _laggard_candidate_for_ticker(
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
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
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
    lag_quality = (
        -1.0 * abs(signal_return)
        + 0.65 * ret20_excess_spy
        + 0.25 * ret60_excess_spy
        + 0.15 * close_location
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.25 * realized_vol20
    )
    return {
        "ticker": ticker,
        "candidate_signal_day_return": round(signal_return, 6),
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
        "candidate_lag_quality_score": round(lag_quality, 6),
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
        "days_with_peer_shocks": 0,
        "days_with_laggard_candidates": 0,
        "days_with_corr_pairs": 0,
        "raw_peer_shocks": 0,
        "raw_laggard_candidates": 0,
        "raw_corr_pairs": 0,
        "min_correlation": MIN_CORRELATION,
        "correlation_lookback_days": CORR_LOOKBACK_DAYS,
        "max_shock_peers_per_day": MAX_SHOCK_PEERS_PER_DAY,
        "max_laggard_candidates_per_day": MAX_LAGGARD_CANDIDATES_PER_DAY,
    }

    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in snapshot)
    for signal_date in dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < CORR_LOOKBACK_DAYS:
            continue
        prior_dates = all_dates[pos - CORR_LOOKBACK_DAYS : pos]

        peer_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _peer_shock_for_ticker(
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
        scan["days_with_peer_shocks"] += 1
        scan["raw_peer_shocks"] += len(peer_rows)
        peer_rows.sort(
            key=lambda row: (
                -float(row["peer_score"]),
                -float(row["peer_signal_day_return"]),
                -float(row["peer_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        peer_rows = peer_rows[:MAX_SHOCK_PEERS_PER_DAY]

        laggard_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _laggard_candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                )
            )
            is not None
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
        for row in [*peer_rows, *laggard_rows]:
            ticker = str(row["ticker"])
            if ticker in vector_by_ticker:
                continue
            vector = _prior_return_vector_for_dates(
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
            for laggard in laggard_rows:
                ticker = str(laggard["ticker"])
                if ticker == peer_ticker:
                    continue
                laggard_vector = vector_by_ticker.get(ticker)
                if laggard_vector is None:
                    continue
                corr = _pearson_corr(peer_vector, laggard_vector)
                if corr is None or corr < MIN_CORRELATION:
                    continue
                same_sector = peer.get("peer_sector") == laggard.get("sector")
                same_industry = peer.get("peer_industry") == laggard.get("industry")
                score = (
                    1.80 * corr
                    + 2.40 * float(peer["peer_relative_vs_spy"])
                    + 1.10 * float(peer["peer_signal_day_return"])
                    + 0.75 * float(laggard["candidate_lag_quality_score"])
                    - 1.20 * max(float(laggard["candidate_signal_day_return"]), 0.0)
                    + (0.08 if same_sector else 0.0)
                    + (0.05 if same_industry else 0.0)
                )
                ab_entries = entries_by_date.get(signal_date, [])
                day_rows.append(
                    {
                        "date": signal_date,
                        "ticker": ticker,
                        "source": "ROLLING_CORR_PEER_SHOCK_LAG_PAPER",
                        "candidate_score": round(score, 6),
                        "peer_ticker": peer_ticker,
                        "rolling_corr_60d": round(corr, 6),
                        "same_sector_as_peer": bool(same_sector),
                        "same_industry_as_peer": bool(same_industry),
                        "peer_signal_day_return": peer["peer_signal_day_return"],
                        "peer_relative_vs_spy": peer["peer_relative_vs_spy"],
                        "peer_volume_ratio_20d": peer["peer_volume_ratio_20d"],
                        "peer_ret20_excess_spy": peer["peer_ret20_excess_spy"],
                        "peer_avg_dollar_volume_20d": peer[
                            "peer_avg_dollar_volume_20d"
                        ],
                        "peer_sector": peer.get("peer_sector"),
                        "peer_industry": peer.get("peer_industry"),
                        **laggard,
                        "same_day_ab_entry_count": len(ab_entries),
                        "same_day_ab_overlap": bool(ab_entries),
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
                -float(row["peer_relative_vs_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("peer_ticker") or ""),
                row["ticker"],
            )
        )
        day_rows = day_rows[:MAX_RAW_ROWS_PER_DAY]
        candidates.extend(day_rows)
        scan["days_with_corr_pairs"] += 1
        scan["raw_corr_pairs"] += len(day_rows)
        peer_contexts.append(
            {
                "date": signal_date,
                "raw_peer_shock_count": len(peer_rows),
                "raw_laggard_candidate_count": len(laggard_rows),
                "corr_pair_count_kept": len(day_rows),
                "top_peer_ticker": day_rows[0]["peer_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_rolling_corr_60d": day_rows[0]["rolling_corr_60d"],
                "top_peer_relative_vs_spy": day_rows[0]["peer_relative_vs_spy"],
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
            -float(row["peer_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("peer_ticker") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_peer_signal_return": MIN_PEER_SIGNAL_RETURN,
            "min_peer_relative_vs_spy": MIN_PEER_RELATIVE_VS_SPY,
            "min_peer_volume_ratio_20d": MIN_PEER_VOLUME_RATIO_20D,
            "min_peer_ret20_excess_spy": MIN_PEER_RET20_EXCESS_SPY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
        }
    )
    return candidates, peer_contexts, scan


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
    gate["decision"] = (
        "positive_replay_lead_not_promoted_rolling_corr_peer_shock_lag"
        if gate["passed"]
        else "rejected_rolling_corr_peer_shock_lag_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "A liquid stock that is highly correlated with a peer that had "
                "an event-like positive shock, but did not move on the signal "
                "day, may be a cleaner next-open candidate than raw own-"
                "momentum or same-industry peer transfer."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "rolling_price_relation_graph_from_free_ohlcv",
            "nearby_prior_experiments": [
                "exp-20260602-020",
                "exp-20260602-021",
                "exp-20260602-029",
                "exp-20260603-005",
                "exp-20260605-024",
                "exp-20260606-004",
                "exp-20260606-006",
                "exp-20260606-014",
                "exp-20260606-015",
            ],
            "prior_trial_count": 9,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that short-horizon price "
                "correlation is too unstable or simply repackages broad beta/"
                "own momentum after peer shocks. Do not answer by sweeping "
                "nearby correlation, peer-shock, hold-day, cooldown, notional, "
                "or top-N thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new relation evidence such as "
                "forward replacement-value rows, production-visible supplier/"
                "customer or product-market links, or true PIT catalyst "
                "provenance. Pure OHLCV correlation threshold retunes should "
                "stay frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "correlation_lookback_days": CORR_LOOKBACK_DAYS,
            "min_correlation": MIN_CORRELATION,
            "max_shock_peers_per_day": MAX_SHOCK_PEERS_PER_DAY,
            "max_laggard_candidates_per_day": MAX_LAGGARD_CANDIDATES_PER_DAY,
            "max_raw_rows_per_day": MAX_RAW_ROWS_PER_DAY,
            "min_peer_signal_return": MIN_PEER_SIGNAL_RETURN,
            "min_peer_relative_vs_spy": MIN_PEER_RELATIVE_VS_SPY,
            "min_peer_volume_ratio_20d": MIN_PEER_VOLUME_RATIO_20D,
            "min_peer_ret20_excess_spy": MIN_PEER_RET20_EXCESS_SPY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "60 prior trading-day returns for correlation. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: trailing-correlation peer shocks may expose "
            "lagged liquid stock reactions using a free PIT relation graph."
        ),
        "2_history_check": {
            "exp-20260602-020/021/029": (
                "Same-sector/exact-industry earnings peer support and transfer "
                "variants failed or were too concentrated. This run does not "
                "use sector taxonomy as the relation; it computes rolling "
                "price correlation known before the candidate entry."
            ),
            "exp-20260603-005 and exp-20260605-024": (
                "Fundamental/same-industry peer confirmation variants failed "
                "or are frozen. This run avoids Companyfacts peer fields."
            ),
            "exp-20260606-004/006/014/015": (
                "Broad 5-day continuation/exhaustion and low-vol breakout "
                "OHLCV scouts failed. This run requires a distinct peer shock "
                "and lagged candidate response, not candidate own 5-day "
                "winner continuation."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_018_rolling_corr_peer_shock_lag_candidate_pool.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The rolling-correlation peer-shock lag candidate source cleared Gate "
        "4 as a replay-only/default-off lead, but no production surface was "
        "promoted. A shared parity adapter is required before use."
        if payload["gate4"]["passed"]
        else (
            "The rolling-correlation peer-shock lag candidate source did not "
            "clear Gate 4; do not promote or locally retune this correlation "
            "peer-lag family on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Peer days | Corr pairs | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {pairs} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("days_with_peer_shocks", 0),
                pairs=scan.get("raw_corr_pairs", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Rolling-Correlation Peer Shock Lag Candidate Pool",
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
                "peer_shock_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_peer_shocks"
                ),
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
