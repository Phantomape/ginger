"""exp-20260609-014: multi-peer correlation-cluster shock candidate pool.

Replay-only alpha search on a free OHLCV high-order relation field. The fixed
bundle tests whether a bounded laggard is cleaner when at least two liquid
prior-correlated peers shock upward on the same signal date. Paper entry is
next-open with the existing 10-trading-day event-sleeve exit.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import exp_20260609_013_asynchronous_lead_lag_peer_catchup as previous


framework = previous.framework

SCRIPTS_DIR = framework.REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_GATE4 = previous.BASE_GATE4

EXPERIMENT_ID = "exp-20260609-014"
STEM = "multi_peer_correlation_cluster_shock"
TRIAL_FAMILY = "multi_peer_correlation_cluster_shock_candidate_pool"
TRIAL_VARIANT_ID = "multi_peer_correlation_cluster_shock_top1_next_open_10d_v1"
CHANGED_VARIABLE = "multi_peer_correlation_cluster_shock_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_014_{STEM}.json"
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
RELATION_LOOKBACK_DAYS = 60
MIN_VALID_PAIR_DAYS = 45
MIN_PEER_CORR = 0.35
MIN_SUPPORTING_PEERS = 2
MAX_SHOCK_LEADERS_PER_DAY = 16
MAX_LAGGARDS_PER_DAY = 450

MIN_LEADER_SIGNAL_RETURN = 0.040
MIN_LEADER_RELATIVE_VS_SPY = 0.025
MIN_LEADER_VOLUME_RATIO_20D = 1.05
MIN_LEADER_CLOSE_LOCATION = 0.60
MIN_LEADER_RET20_EXCESS_SPY = -0.020

MIN_LAGGARD_SIGNAL_RETURN = 0.0
MAX_LAGGARD_SIGNAL_RETURN = 0.030
MIN_LAGGARD_RELATIVE_VS_SPY = -0.010
MIN_LAGGARD_CLOSE_LOCATION = 0.38
MIN_LAGGARD_RET5 = -0.060
MAX_LAGGARD_RET5 = 0.060
MIN_LAGGARD_RET20_EXCESS_SPY = -0.040
MIN_LAGGARD_RET60_EXCESS_SPY = -0.080
MAX_LAGGARD_REALIZED_VOL_20D = 0.095
MIN_AVG_LEADER_GAP = 0.020

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ROLLING_CORR_COMPARATOR = {
    "experiment_id": "exp-20260606-025",
    "decision": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.3845,
    "total_pnl_delta_sum": 6107.66,
    "target_trade_count": 48,
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "rolling_corr_peer_shock_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "correlation_mining_without_causal_story",
        "thin_sample",
    ],
    "confidence_reason": (
        "Accepted rolling-correlation peer shock proves dynamic peer edges can "
        "work; recent failures show static sector labels and one-day lag are "
        "insufficient. Multi-peer same-day confirmation is a materially "
        "different high-order relation field but may still be correlation "
        "mining."
    ),
    "recorded_at": "2026-06-09T13:06:11Z",
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
        "require a shared default-off adapter computing the same same-day "
        "multi-peer shock leaders, prior-60-day correlation support, bounded "
        "laggard fields, overlap exclusion, next-open paper entry, 10-trading-"
        "day exit, costs, cooldown, accepted comparator, and concentration "
        "controls in historical replay and daily production before any report "
        "queue, paper ledger, candidate priority, sizing, watchlist, or order "
        "surface could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _pearson_corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < MIN_VALID_PAIR_DAYS:
        return None
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    x_var = sum((value - x_mean) ** 2 for value in xs)
    y_var = sum((value - y_mean) ** 2 for value in ys)
    if x_var <= 0.0 or y_var <= 0.0:
        return None
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    return cov / math.sqrt(x_var * y_var)


def _same_day_vectors(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    leader_ticker: str,
    laggard_ticker: str,
    prior_dates: list[str],
) -> tuple[list[float], list[float]]:
    leader_rows = snapshot.get(leader_ticker) or []
    laggard_rows = snapshot.get(laggard_ticker) or []
    leader_idx = indices.get(leader_ticker, {})
    laggard_idx = indices.get(laggard_ticker, {})
    leader_values: list[float] = []
    laggard_values: list[float] = []
    for day in prior_dates:
        leader_pos = leader_idx.get(day)
        laggard_pos = laggard_idx.get(day)
        if leader_pos is None or laggard_pos is None:
            continue
        leader_value = framework._daily_return(leader_rows, leader_pos)
        laggard_value = framework._daily_return(laggard_rows, laggard_pos)
        if leader_value is None or laggard_value is None:
            continue
        leader_values.append(float(leader_value))
        laggard_values.append(float(laggard_value))
    return leader_values, laggard_values


def _shock_leader_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    if ticker in framework.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < RELATION_LOOKBACK_DAYS or spy_idx < 20:
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
    required = [signal_return, spy_return, volume_ratio, close_location, ret20, spy_ret20]
    if any(value is None for value in required):
        return None
    assert signal_return is not None
    assert spy_return is not None
    assert volume_ratio is not None
    assert close_location is not None
    assert ret20 is not None
    assert spy_ret20 is not None
    relative_vs_spy = signal_return - spy_return
    ret20_excess_spy = ret20 - spy_ret20
    if signal_return < MIN_LEADER_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_LEADER_RELATIVE_VS_SPY:
        return None
    if volume_ratio < MIN_LEADER_VOLUME_RATIO_20D:
        return None
    if close_location < MIN_LEADER_CLOSE_LOCATION:
        return None
    if ret20_excess_spy < MIN_LEADER_RET20_EXCESS_SPY:
        return None
    sector_meta = sector_entries[ticker]
    score = (
        3.0 * signal_return
        + 2.2 * relative_vs_spy
        + 0.40 * ret20_excess_spy
        + 0.12 * min(volume_ratio, 5.0)
        + 0.25 * close_location
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "ticker": ticker,
        "leader_signal_return": round(signal_return, 6),
        "leader_relative_vs_spy": round(relative_vs_spy, 6),
        "leader_volume_ratio_20d": round(volume_ratio, 6),
        "leader_close_location": round(close_location, 6),
        "leader_ret20_excess_spy": round(ret20_excess_spy, 6),
        "leader_avg_dollar_volume_20d": round(adv20, 2),
        "leader_score": round(score, 6),
        "leader_sector": sector_meta.get("sector"),
        "leader_industry": sector_meta.get("industry"),
    }


def _laggard_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    if ticker in framework.EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < RELATION_LOOKBACK_DAYS or spy_idx < 60:
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
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
        spy_return,
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
    assert spy_return is not None
    assert close_location is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    relative_vs_spy = signal_return - spy_return
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < MIN_LAGGARD_SIGNAL_RETURN:
        return None
    if signal_return > MAX_LAGGARD_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_LAGGARD_RELATIVE_VS_SPY:
        return None
    if close_location < MIN_LAGGARD_CLOSE_LOCATION:
        return None
    if ret5 < MIN_LAGGARD_RET5 or ret5 > MAX_LAGGARD_RET5:
        return None
    if ret20_excess_spy < MIN_LAGGARD_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_LAGGARD_RET60_EXCESS_SPY:
        return None
    if realized_vol20 > MAX_LAGGARD_REALIZED_VOL_20D:
        return None
    sector_meta = sector_entries[ticker]
    quality = (
        0.70 * ret20_excess_spy
        + 0.35 * ret60_excess_spy
        + 0.24 * close_location
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.45 * abs(signal_return)
        - 0.20 * max(ret5, 0.0)
        - 0.35 * realized_vol20
        + 0.03 * min(volume_ratio, 3.0)
    )
    return {
        "ticker": ticker,
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "candidate_quality_score": round(quality, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
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
    date_pos = {day: pos for pos, day in enumerate(all_dates)}
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in snapshot)
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_shock_leaders": 0,
        "days_with_laggard_candidates": 0,
        "days_with_multi_peer_supported_candidates": 0,
        "raw_shock_leaders": 0,
        "raw_laggard_candidates": 0,
        "raw_supported_candidate_rows": 0,
        "relation_lookback_days": RELATION_LOOKBACK_DAYS,
        "min_valid_pair_days": MIN_VALID_PAIR_DAYS,
        "min_peer_corr": MIN_PEER_CORR,
        "min_supporting_peers": MIN_SUPPORTING_PEERS,
    }
    for signal_date in dates:
        pos = date_pos.get(signal_date)
        if pos is None or pos < RELATION_LOOKBACK_DAYS:
            continue
        prior_dates = all_dates[pos - RELATION_LOOKBACK_DAYS : pos]
        leaders = [
            row
            for ticker in eligible_tickers
            if (
                row := _shock_leader_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                )
            )
            is not None
        ]
        if not leaders:
            continue
        scan["days_with_shock_leaders"] += 1
        scan["raw_shock_leaders"] += len(leaders)
        leaders.sort(
            key=lambda row: (
                -float(row["leader_score"]),
                -float(row["leader_signal_return"]),
                -float(row["leader_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        leaders = leaders[:MAX_SHOCK_LEADERS_PER_DAY]

        laggards = [
            row
            for ticker in eligible_tickers
            if (
                row := _laggard_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                )
            )
            is not None
        ]
        if not laggards:
            continue
        scan["days_with_laggard_candidates"] += 1
        scan["raw_laggard_candidates"] += len(laggards)
        laggards.sort(
            key=lambda row: (
                -float(row["candidate_quality_score"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        laggards = laggards[:MAX_LAGGARDS_PER_DAY]

        ab_entries = entries_by_date.get(signal_date, [])
        day_rows: list[dict[str, Any]] = []
        for laggard in laggards:
            ticker = str(laggard["ticker"])
            supporting: list[dict[str, Any]] = []
            for leader in leaders:
                leader_ticker = str(leader["ticker"])
                if leader_ticker == ticker:
                    continue
                xs, ys = _same_day_vectors(
                    snapshot=snapshot,
                    indices=indices,
                    leader_ticker=leader_ticker,
                    laggard_ticker=ticker,
                    prior_dates=prior_dates,
                )
                corr = _pearson_corr(xs, ys)
                if corr is None or corr < MIN_PEER_CORR:
                    continue
                gap = float(leader["leader_signal_return"]) - float(
                    laggard["candidate_signal_day_return"]
                )
                if gap < MIN_AVG_LEADER_GAP:
                    continue
                supporting.append(
                    {
                        "leader_ticker": leader_ticker,
                        "peer_corr_60d": round(corr, 6),
                        "pair_count": len(xs),
                        "leader_signal_return": leader["leader_signal_return"],
                        "leader_relative_vs_spy": leader["leader_relative_vs_spy"],
                        "leader_volume_ratio_20d": leader["leader_volume_ratio_20d"],
                        "leader_sector": leader.get("leader_sector"),
                        "leader_industry": leader.get("leader_industry"),
                        "leader_minus_laggard_return_gap": round(gap, 6),
                    }
                )
            if len(supporting) < MIN_SUPPORTING_PEERS:
                continue
            supporting.sort(
                key=lambda row: (
                    -float(row["peer_corr_60d"]),
                    -float(row["leader_signal_return"]),
                    row["leader_ticker"],
                )
            )
            top_support = supporting[:6]
            avg_corr = sum(float(row["peer_corr_60d"]) for row in top_support) / len(
                top_support
            )
            avg_gap = sum(
                float(row["leader_minus_laggard_return_gap"]) for row in top_support
            ) / len(top_support)
            avg_leader_relative = sum(
                float(row["leader_relative_vs_spy"]) for row in top_support
            ) / len(top_support)
            same_sector_support = sum(
                1 for row in top_support if row.get("leader_sector") == laggard.get("sector")
            )
            score = (
                1.60 * avg_corr
                + 0.38 * min(len(top_support), 6)
                + 1.45 * avg_gap
                + 1.15 * avg_leader_relative
                + 0.80 * float(laggard["candidate_quality_score"])
                - 0.35 * max(float(laggard["candidate_signal_day_return"]), 0.0)
                + 0.04 * same_sector_support
            )
            day_rows.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "MULTI_PEER_CORRELATION_CLUSTER_SHOCK_PAPER",
                    "candidate_score": round(score, 6),
                    "supporting_peer_count": len(top_support),
                    "all_supporting_peer_count": len(supporting),
                    "avg_peer_corr_60d": round(avg_corr, 6),
                    "avg_leader_laggard_return_gap": round(avg_gap, 6),
                    "avg_leader_relative_vs_spy": round(avg_leader_relative, 6),
                    "same_sector_supporting_peer_count": same_sector_support,
                    "supporting_peers": top_support,
                    "same_day_ab_entry_count": len(ab_entries),
                    "same_day_ab_overlap": bool(ab_entries),
                    "same_ticker_ab_overlap": any(
                        str(entry.get("ticker") or "").upper() == ticker
                        for entry in ab_entries
                    ),
                    "rule_version": RULE_VERSION,
                    "uses_free_ohlcv_only": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "known_at": "after_signal_day_close_before_next_open_paper_entry",
                    **laggard,
                }
            )
        if not day_rows:
            continue
        scan["days_with_multi_peer_supported_candidates"] += 1
        scan["raw_supported_candidate_rows"] += len(day_rows)
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["supporting_peer_count"]),
                -float(row["avg_peer_corr_60d"]),
                -float(row["avg_leader_laggard_return_gap"]),
                -float(row["candidate_quality_score"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "shock_leader_count": len(leaders),
                "laggard_candidate_count": len(laggards),
                "multi_peer_supported_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_supporting_peer_count": day_rows[0]["supporting_peer_count"],
                "top_avg_peer_corr_60d": day_rows[0]["avg_peer_corr_60d"],
                "top_avg_leader_laggard_return_gap": day_rows[0][
                    "avg_leader_laggard_return_gap"
                ],
                "top_supporting_peers": day_rows[0]["supporting_peers"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["supporting_peer_count"]),
            -float(row["avg_peer_corr_60d"]),
            -float(row["avg_leader_laggard_return_gap"]),
            row["ticker"],
        )
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
    if aggregate["expected_value_score_delta_sum"] <= ROLLING_CORR_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("rolling_corr_peer_shock_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ROLLING_CORR_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("rolling_corr_peer_shock_pnl_not_beaten")
    gate["rolling_corr_peer_shock_comparator"] = ROLLING_CORR_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_multi_peer_correlation_cluster_shock"
        if gate["passed"]
        else "rejected_multi_peer_correlation_cluster_shock_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "High-order same-day correlation-cluster peer shocks may "
                "identify bounded laggards with cleaner replacement value than "
                "single-peer shock or static sector transfer."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_high_order_relation_alpha",
            "new_evidence_type": "production_visible_free_ohlcv_high_order_relation_cluster",
            "nearby_prior_experiments": [
                "exp-20260606-025",
                "exp-20260608-023",
                "exp-20260608-025",
                "exp-20260608-028",
                "exp-20260609-013",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "rolling_corr_peer_shock_comparator": ROLLING_CORR_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that multi-peer same-day "
                "correlation support still mines broad momentum/correlation "
                "rather than a durable displacement relation. Do not answer by "
                "sweeping correlation, support count, leader shock, laggard "
                "return, top-N, hold-day, cooldown, or notional thresholds on "
                "these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs a materially different PIT relation source such "
                "as customer/supplier links, source-provenanced event transfer, "
                "or forward replacement-value rows versus accepted relation "
                "comparators. Pure OHLCV high-order-correlation retunes should "
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
            "relation_lookback_days": RELATION_LOOKBACK_DAYS,
            "min_valid_pair_days": MIN_VALID_PAIR_DAYS,
            "min_peer_corr": MIN_PEER_CORR,
            "min_supporting_peers": MIN_SUPPORTING_PEERS,
            "max_shock_leaders_per_day": MAX_SHOCK_LEADERS_PER_DAY,
            "max_laggards_per_day": MAX_LAGGARDS_PER_DAY,
            "min_leader_signal_return": MIN_LEADER_SIGNAL_RETURN,
            "min_leader_relative_vs_spy": MIN_LEADER_RELATIVE_VS_SPY,
            "min_leader_volume_ratio_20d": MIN_LEADER_VOLUME_RATIO_20D,
            "min_laggard_signal_return": MIN_LAGGARD_SIGNAL_RETURN,
            "max_laggard_signal_return": MAX_LAGGARD_SIGNAL_RETURN,
            "min_avg_leader_gap": MIN_AVG_LEADER_GAP,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: a bounded laggard supported by multiple "
            "same-day shocked, prior-correlated peers may represent a stronger "
            "high-order relation than one shocked peer or a sector label."
        ),
        "2_history_check": {
            "exp-20260606-025": (
                "Accepted rolling-correlation peer shock is the closest "
                "comparator; this run must beat it before promotion."
            ),
            "exp-20260608-023": (
                "Sector-level peer transfer was too broad and tail-risky; this "
                "uses ticker-level rolling correlations and multiple leaders."
            ),
            "exp-20260608-025": (
                "Same-industry characteristic similarity did not encode a "
                "strong enough edge; this run uses dynamic price relations."
            ),
            "exp-20260608-028": (
                "Negative peer-shock substitute logic failed the comparator; "
                "this only tests positive multi-peer information shocks."
            ),
            "exp-20260609-013": (
                "Asynchronous one-day lag failed all windows; this uses same-day "
                "high-order peer confirmation, not lag timing."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md canonical three windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all three windows, survival >=5%, drawdown "
            "drift <=0.5pp, concentration guard passes, and accepted rolling-"
            "corr peer-shock comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_014_multi_peer_correlation_cluster_shock.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted" if payload["gate4"]["passed"] else "rejected"
    )
    payload["interpretation"] = (
        "The multi-peer correlation-cluster shock source cleared Gate 4 and "
        "beat the accepted rolling-correlation peer-shock comparator, but "
        "remains replay-only until a shared default-off adapter reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The multi-peer correlation-cluster shock source did not clear "
            "Gate 4 or did not beat the accepted rolling-correlation peer-"
            "shock comparator; do not promote or locally retune this high-order "
            "correlation family on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "A high-order peer cluster has to beat the accepted single-peer "
            "relation sleeve. If it fails, the extra peers likely add broad "
            "momentum/correlation exposure rather than a stronger displacement "
            "edge after next-open execution and costs."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping relation lookback, min correlation, "
            "supporting peer count, leader shock thresholds, laggard return "
            "bounds, top-N, hold-day, cooldown, or paper notional thresholds "
            "on these frozen windows."
        ),
        "new_evidence_required": (
            "Need forward replacement-value rows or a materially new PIT "
            "relation edge such as customer/supplier, source-provenanced event "
            "transfer, or external causal channel evidence before revisiting."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Shock days | Cluster days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {shock_days} | {cluster_days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                shock_days=scan.get("days_with_shock_leaders", 0),
                cluster_days=scan.get("days_with_multi_peer_supported_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Multi-Peer Correlation-Cluster Shock",
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
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ROLLING_CORR_COMPARATOR["expected_value_score_delta_sum"],
                ROLLING_CORR_COMPARATOR["total_pnl_delta_sum"],
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
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_high_order_relation_alpha",
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
        "rolling_corr_peer_shock_comparator": ROLLING_CORR_COMPARATOR,
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
                "shock_leader_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_shock_leaders"
                ),
                "multi_peer_supported_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_multi_peer_supported_candidates"),
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


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "calibration": payload["calibration"],
        "gate4": payload["gate4"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
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
        "aggregate_expected_value_delta": log_record[
            "aggregate_expected_value_delta"
        ],
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
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
