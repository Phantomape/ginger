"""exp-20260610-022: rolling lead-lag peer underreaction scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
relation source: a liquid peer that moved strongly on the previous trading day
may lead a related liquid stock on the next day when the candidate has not
already chased and has a positive signal-day response.

The relation edge is not same-day correlation. It is a rolling lead-lag
correlation: prior peer day return versus next-day candidate return, using only
history available before the signal day. This is intentionally a private replay
scout because the data shape is uncertain; a positive result is only a lead
until a shared default-off helper and daily snapshot parity reproduce it.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import exp_20260606_018_rolling_corr_peer_shock_lag_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260610-022"
STEM = "rolling_lead_lag_peer_underreaction"
TRIAL_FAMILY = "rolling_lead_lag_peer_underreaction_candidate_pool"
TRIAL_VARIANT_ID = "lead_lag_positive_peer_move_top1_next_open_10d_v1"
CHANGED_VARIABLE = "rolling_lead_lag_peer_underreaction_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_022_{STEM}.json"
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

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = previous.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = previous.MIN_AVG_DOLLAR_VOLUME_20D
LEAD_LAG_LOOKBACK_DAYS = 60
MIN_LEAD_LAG_OBSERVATIONS = 45
MIN_LEAD_LAG_CORRELATION = 0.12
MAX_SHOCK_PEERS_PER_DAY = 14
MAX_CANDIDATES_PER_DAY = 450
MAX_RAW_ROWS_PER_DAY = 60

MIN_PEER_PRIOR_RETURN = 0.040
MIN_PEER_PRIOR_RELATIVE_VS_SPY = 0.025
MIN_PEER_PRIOR_VOLUME_RATIO_20D = 1.00
MIN_PEER_RET20_EXCESS_SPY = -0.03

MIN_CANDIDATE_SIGNAL_RETURN = -0.004
MAX_CANDIDATE_SIGNAL_RETURN = 0.032
MIN_CANDIDATE_CLOSE_LOCATION = 0.45
MIN_CANDIDATE_PRIOR_DAY_RETURN = -0.040
MAX_CANDIDATE_PRIOR_DAY_RETURN = 0.018
MAX_CANDIDATE_PRIOR_DAY_RELATIVE_TO_PEER = -0.015
MIN_CANDIDATE_RET5 = -0.055
MAX_CANDIDATE_RET5 = 0.070
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.040
MAX_CANDIDATE_RET20_EXCESS_SPY = 0.160
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.090
MAX_CANDIDATE_REALIZED_VOL_20D = 0.100

MIN_TARGET_TRADES = previous.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = previous.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2200.0,
    "main_failure_modes": [
        "lead_lag_edge_unstable",
        "accepted_peer_shock_comparator_not_beaten",
        "window_regression",
        "concentration_failed",
        "thin_sample",
    ],
    "confidence_reason": (
        "Accepted rolling-correlation peer shock proves relation-specific "
        "OHLCV edges can work, but many sector/industry peer variants failed. "
        "This tests a materially different lagged edge construction with only "
        "signal-date and prior OHLCV; data-shape and comparator risk keep "
        "confidence low."
    ),
    "recorded_at": "2026-06-10T20:06:35+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_dynamic_lead_lag_relation_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "max_active_positions": 8,
        "liquidity_source": "signal-date price >= $10 and ADV20 >= $50M",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": (
            "replay-only paper overlay versus core baseline; no live portfolio "
            "or accepted allocator displacement"
        ),
        "kill_switch": (
            "not live; positive replay requires shared helper parity, forward "
            "replacement-value rows, and a separate activation envelope"
        ),
    },
    "parity_note": (
        "This experiment changes no production path. The lead-lag edge uses "
        "free OHLCV fields that a daily default-off helper could compute, but "
        "no helper is promoted here. Any positive result remains a replay lead "
        "until the same edge, candidate gates, next-open paper entry, 10-day "
        "exit, costs, cooldown, core-overlap exclusion, comparator, and "
        "concentration controls are implemented in shared replay and daily "
        "snapshot code."
    ),
}

BASE_BUILD_PAYLOAD = previous._build_payload
BASE_BUILD_LOG_RECORD = previous._build_log_record
BASE_GATE4 = previous.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _lead_lag_correlation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    all_dates: list[str],
    peer_ticker: str,
    candidate_ticker: str,
    signal_pos: int,
) -> dict[str, Any] | None:
    peer_rows = snapshot.get(peer_ticker) or []
    candidate_rows = snapshot.get(candidate_ticker) or []
    peer_index = indices.get(peer_ticker, {})
    candidate_index = indices.get(candidate_ticker, {})
    left: list[float] = []
    right: list[float] = []
    start = max(1, signal_pos - LEAD_LAG_LOOKBACK_DAYS)
    for candidate_pos in range(start, signal_pos):
        candidate_day = all_dates[candidate_pos]
        peer_day = all_dates[candidate_pos - 1]
        peer_idx = peer_index.get(peer_day)
        candidate_idx = candidate_index.get(candidate_day)
        if peer_idx is None or candidate_idx is None:
            continue
        peer_return = framework._daily_return(peer_rows, peer_idx)
        candidate_return = framework._daily_return(candidate_rows, candidate_idx)
        if peer_return is None or candidate_return is None:
            continue
        left.append(float(peer_return))
        right.append(float(candidate_return))
    if len(left) < MIN_LEAD_LAG_OBSERVATIONS:
        return None
    corr = previous._pearson_corr(left, right)
    if corr is None or corr < MIN_LEAD_LAG_CORRELATION:
        return None
    return {
        "lead_lag_corr": round(corr, 6),
        "lead_lag_observation_count": len(left),
    }


def _prior_peer_shock_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    prior_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(prior_date)
    spy_idx = indices.get("SPY", {}).get(prior_date)
    if idx is None or spy_idx is None or idx < LEAD_LAG_LOOKBACK_DAYS + 1 or spy_idx < 20:
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
    if signal_return < MIN_PEER_PRIOR_RETURN:
        return None
    if relative_vs_spy < MIN_PEER_PRIOR_RELATIVE_VS_SPY:
        return None
    if volume_ratio < MIN_PEER_PRIOR_VOLUME_RATIO_20D:
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
        "peer_prior_date": prior_date,
        "peer_signal_date": signal_date,
        "peer_prior_day_return": round(signal_return, 6),
        "peer_prior_relative_vs_spy": round(relative_vs_spy, 6),
        "peer_prior_volume_ratio_20d": round(volume_ratio, 6),
        "peer_ret20_excess_spy": round(ret20_excess_spy, 6),
        "peer_avg_dollar_volume_20d": round(adv20, 2),
        "peer_score": round(score, 6),
        "peer_sector": sector_meta.get("sector"),
        "peer_industry": sector_meta.get("industry"),
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    prior_date: str,
    best_peer: dict[str, Any],
    lead_lag: dict[str, Any],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    prior_idx = indices.get(ticker, {}).get(prior_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or prior_idx is None or spy_idx is None:
        return None
    if idx < LEAD_LAG_LOOKBACK_DAYS + 1 or spy_idx < 60 or idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    prior_day_return = framework._daily_return(rows, prior_idx)
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
        prior_day_return,
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
    assert prior_day_return is not None
    assert close_location is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    prior_day_relative_to_peer = prior_day_return - float(best_peer["peer_prior_day_return"])
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if signal_return > MAX_CANDIDATE_SIGNAL_RETURN:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if prior_day_return < MIN_CANDIDATE_PRIOR_DAY_RETURN:
        return None
    if prior_day_return > MAX_CANDIDATE_PRIOR_DAY_RETURN:
        return None
    if prior_day_relative_to_peer > MAX_CANDIDATE_PRIOR_DAY_RELATIVE_TO_PEER:
        return None
    if ret5 < MIN_CANDIDATE_RET5 or ret5 > MAX_CANDIDATE_RET5:
        return None
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret20_excess_spy > MAX_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if realized_vol20 > MAX_CANDIDATE_REALIZED_VOL_20D:
        return None
    sector_meta = sector_entries[ticker]
    same_sector = best_peer.get("peer_sector") == sector_meta.get("sector")
    same_industry = best_peer.get("peer_industry") == sector_meta.get("industry")
    lead_lag_corr = float(lead_lag["lead_lag_corr"])
    lag_quality = (
        1.25 * lead_lag_corr
        + 1.20 * float(best_peer["peer_prior_relative_vs_spy"])
        + 0.65 * signal_return
        + 0.55 * ret20_excess_spy
        + 0.22 * ret60_excess_spy
        + 0.18 * close_location
        + 0.05 * min(volume_ratio, 3.0)
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        + (0.08 if same_sector else 0.0)
        + (0.05 if same_industry else 0.0)
        - 0.45 * abs(signal_return - 0.010)
        - 0.30 * max(ret5, 0.0)
        - 0.28 * realized_vol20
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "ROLLING_LEAD_LAG_PEER_UNDERREACTION_PAPER",
        "candidate_score": round(lag_quality, 6),
        "peer_ticker": best_peer["ticker"],
        "peer_prior_date": prior_date,
        "lead_lag_corr_60d": round(lead_lag_corr, 6),
        "lead_lag_observation_count": lead_lag["lead_lag_observation_count"],
        "same_sector_as_peer": bool(same_sector),
        "same_industry_as_peer": bool(same_industry),
        "peer_prior_day_return": best_peer["peer_prior_day_return"],
        "peer_prior_relative_vs_spy": best_peer["peer_prior_relative_vs_spy"],
        "peer_prior_volume_ratio_20d": best_peer["peer_prior_volume_ratio_20d"],
        "peer_ret20_excess_spy": best_peer["peer_ret20_excess_spy"],
        "peer_avg_dollar_volume_20d": best_peer["peer_avg_dollar_volume_20d"],
        "peer_sector": best_peer.get("peer_sector"),
        "peer_industry": best_peer.get("peer_industry"),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_prior_day_return": round(prior_day_return, 6),
        "candidate_prior_day_relative_to_peer": round(prior_day_relative_to_peer, 6),
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
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
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
    lead_lag_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_prior_peer_shocks": 0,
        "days_with_lead_lag_pairs": 0,
        "raw_prior_peer_shocks": 0,
        "raw_lead_lag_pairs": 0,
        "lead_lag_lookback_days": LEAD_LAG_LOOKBACK_DAYS,
        "min_lead_lag_observations": MIN_LEAD_LAG_OBSERVATIONS,
        "min_lead_lag_correlation": MIN_LEAD_LAG_CORRELATION,
        "max_shock_peers_per_day": MAX_SHOCK_PEERS_PER_DAY,
        "max_candidates_per_day": MAX_CANDIDATES_PER_DAY,
    }

    eligible_tickers = sorted(ticker for ticker in sector_entries if ticker in snapshot)
    for signal_date in dates:
        signal_pos = date_pos.get(signal_date)
        if signal_pos is None or signal_pos < LEAD_LAG_LOOKBACK_DAYS + 1:
            continue
        prior_date = all_dates[signal_pos - 1]

        peer_rows = [
            row
            for ticker in eligible_tickers
            if (
                row := _prior_peer_shock_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    prior_date=prior_date,
                )
            )
            is not None
        ]
        if not peer_rows:
            continue
        scan["days_with_prior_peer_shocks"] += 1
        scan["raw_prior_peer_shocks"] += len(peer_rows)
        peer_rows.sort(
            key=lambda row: (
                -float(row["peer_score"]),
                -float(row["peer_prior_day_return"]),
                -float(row["peer_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        peer_rows = peer_rows[:MAX_SHOCK_PEERS_PER_DAY]

        day_rows: list[dict[str, Any]] = []
        for candidate_ticker in eligible_tickers:
            if candidate_ticker not in snapshot:
                continue
            candidate_pair_rows: list[dict[str, Any]] = []
            for peer in peer_rows:
                peer_ticker = str(peer["ticker"])
                if peer_ticker == candidate_ticker:
                    continue
                lead_lag = _lead_lag_correlation(
                    snapshot=snapshot,
                    indices=indices,
                    all_dates=all_dates,
                    peer_ticker=peer_ticker,
                    candidate_ticker=candidate_ticker,
                    signal_pos=signal_pos,
                )
                if lead_lag is None:
                    continue
                row = _candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=candidate_ticker,
                    signal_date=signal_date,
                    prior_date=prior_date,
                    best_peer=peer,
                    lead_lag=lead_lag,
                )
                if row is not None:
                    candidate_pair_rows.append(row)
            if not candidate_pair_rows:
                continue
            candidate_pair_rows.sort(
                key=lambda row: (
                    -float(row["candidate_score"]),
                    -float(row["lead_lag_corr_60d"]),
                    -float(row["peer_prior_relative_vs_spy"]),
                    str(row.get("peer_ticker") or ""),
                    row["ticker"],
                )
            )
            day_rows.append(candidate_pair_rows[0])

        if not day_rows:
            continue
        scan["days_with_lead_lag_pairs"] += 1
        scan["raw_lead_lag_pairs"] += len(day_rows)
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["lead_lag_corr_60d"]),
                -float(row["peer_prior_relative_vs_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("peer_ticker") or ""),
                row["ticker"],
            )
        )
        day_rows = day_rows[:MAX_RAW_ROWS_PER_DAY]
        ab_entries = entries_by_date.get(signal_date, [])
        for row in day_rows:
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
        candidates.extend(day_rows)
        lead_lag_contexts.append(
            {
                "date": signal_date,
                "prior_date": prior_date,
                "raw_prior_peer_shock_count": len(peer_rows),
                "lead_lag_pair_count_kept": len(day_rows),
                "top_peer_ticker": day_rows[0]["peer_ticker"],
                "top_candidate": day_rows[0]["ticker"],
                "top_score": day_rows[0]["candidate_score"],
                "top_lead_lag_corr_60d": day_rows[0]["lead_lag_corr_60d"],
                "top_peer_prior_relative_vs_spy": day_rows[0][
                    "peer_prior_relative_vs_spy"
                ],
                "top_candidate_signal_day_return": day_rows[0][
                    "candidate_signal_day_return"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["lead_lag_corr_60d"]),
            -float(row["peer_prior_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("peer_ticker") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_peer_prior_return": MIN_PEER_PRIOR_RETURN,
            "min_peer_prior_relative_vs_spy": MIN_PEER_PRIOR_RELATIVE_VS_SPY,
            "min_peer_prior_volume_ratio_20d": MIN_PEER_PRIOR_VOLUME_RATIO_20D,
            "min_peer_ret20_excess_spy": MIN_PEER_RET20_EXCESS_SPY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_prior_day_return": MIN_CANDIDATE_PRIOR_DAY_RETURN,
            "max_candidate_prior_day_return": MAX_CANDIDATE_PRIOR_DAY_RETURN,
            "max_candidate_prior_day_relative_to_peer": (
                MAX_CANDIDATE_PRIOR_DAY_RELATIVE_TO_PEER
            ),
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
        }
    )
    return candidates, lead_lag_contexts, scan


def _accepted_peer_shock_comparator() -> dict[str, Any]:
    if not ACCEPTED_PEER_SHOCK_ARTIFACT.exists():
        return {
            "available": False,
            "artifact": _repo_rel(ACCEPTED_PEER_SHOCK_ARTIFACT),
            "reason": "missing_accepted_peer_shock_artifact",
        }
    payload = json.loads(ACCEPTED_PEER_SHOCK_ARTIFACT.read_text(encoding="utf-8"))
    gate = payload.get("gate4", {})
    windows = {}
    for row in payload.get("windows") or []:
        label = row.get("label")
        if label:
            windows[label] = {
                "ev": row.get("expected_value_delta"),
                "pnl": row.get("strategy_total_pnl_delta"),
            }
    return {
        "available": True,
        "experiment_id": ACCEPTED_PEER_SHOCK_EXPERIMENT_ID,
        "artifact": _repo_rel(ACCEPTED_PEER_SHOCK_ARTIFACT),
        "decision": payload.get("decision"),
        "aggregate_ev_delta": gate.get("aggregate_ev_delta")
        or payload.get("aggregate_expected_value_delta"),
        "aggregate_pnl_delta": gate.get("aggregate_pnl_delta")
        or payload.get("aggregate_strategy_total_pnl_delta"),
        "target_trade_count": gate.get("target_trade_count"),
        "window_deltas": windows,
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
    failed = list(gate.get("failed_reasons") or [])
    comparator = _accepted_peer_shock_comparator()
    if comparator.get("available"):
        comparator_ev = comparator.get("aggregate_ev_delta")
        comparator_pnl = comparator.get("aggregate_pnl_delta")
        if comparator_ev is not None and float(aggregate["expected_value_score_delta_sum"]) <= float(
            comparator_ev
        ):
            failed.append("accepted_peer_shock_ev_comparator_not_beaten")
        if comparator_pnl is not None and float(aggregate["total_pnl_delta_sum"]) <= float(
            comparator_pnl
        ):
            failed.append("accepted_peer_shock_pnl_comparator_not_beaten")
    else:
        failed.append("accepted_peer_shock_comparator_missing")

    numeric_passed = not failed
    gate.update(
        {
            "numeric_passed": numeric_passed,
            "passed": False,
            "failed_reasons": (
                ["shared_helper_not_promoted"] if numeric_passed else failed
            ),
            "numeric_failed_reasons": failed,
            "accepted_peer_shock_comparator": comparator,
            "requires_shared_adapter_before_promotion": True,
            "decision": (
                "positive_replay_lead_not_promoted_rolling_lead_lag_peer_underreaction"
                if numeric_passed
                else "rejected_rolling_lead_lag_peer_underreaction_candidate_pool"
            ),
        }
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    numeric_passed = bool(payload["gate4"].get("numeric_passed"))
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Lagged lead-lag OHLCV relations may identify liquid stocks "
                "that underreact one trading day after a strongly related peer "
                "moves first, adding a distinct free-data candidate-pool source "
                "beyond same-day rolling-correlation peer shock."
            ),
            "change_type": "candidate_pool_private_replay_scout",
            "implementation_mode": "private_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "new_dynamic_lead_lag_edge_construction",
            "nearby_prior_experiments": [
                "exp-20260606-024",
                "exp-20260606-025",
                "exp-20260608-025",
                "exp-20260608-028",
                "exp-20260610-003",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_peer_shock_comparator": payload["gate4"].get(
                "accepted_peer_shock_comparator"
            ),
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the most likely cause is that a simple 60-day "
                "lead-lag edge is unstable, too close to broad beta, or too "
                "weak versus the accepted same-day rolling-correlation "
                "peer-shock helper after costs. Do not answer by sweeping "
                "lead-lag correlation, peer return, candidate return, top-N, "
                "hold-day, cooldown, or notional thresholds on these frozen "
                "windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially richer PIT relation provenance such "
                "as supplier/customer links, product-line text links, event "
                "source propagation, or closed forward replacement-value rows. "
                "Pure OHLCV lead-lag threshold retunes should stay frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "lead_lag_lookback_days": LEAD_LAG_LOOKBACK_DAYS,
            "min_lead_lag_observations": MIN_LEAD_LAG_OBSERVATIONS,
            "min_lead_lag_correlation": MIN_LEAD_LAG_CORRELATION,
            "max_shock_peers_per_day": MAX_SHOCK_PEERS_PER_DAY,
            "max_candidates_per_day": MAX_CANDIDATES_PER_DAY,
            "max_raw_rows_per_day": MAX_RAW_ROWS_PER_DAY,
            "min_peer_prior_return": MIN_PEER_PRIOR_RETURN,
            "min_peer_prior_relative_vs_spy": MIN_PEER_PRIOR_RELATIVE_VS_SPY,
            "min_peer_prior_volume_ratio_20d": MIN_PEER_PRIOR_VOLUME_RATIO_20D,
            "min_peer_ret20_excess_spy": MIN_PEER_RET20_EXCESS_SPY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_prior_day_return": MIN_CANDIDATE_PRIOR_DAY_RETURN,
            "max_candidate_prior_day_return": MAX_CANDIDATE_PRIOR_DAY_RETURN,
            "max_candidate_prior_day_relative_to_peer": (
                MAX_CANDIDATE_PRIOR_DAY_RELATIVE_TO_PEER
            ),
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date, "
        "the previous trading day's peer move, and 60 prior lead-lag return "
        "pairs. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: a rolling lead-lag edge may capture a "
            "stock-specific delayed reaction after a related peer moves first."
        ),
        "2_history_check": {
            "exp-20260606-024/025": (
                "Accepted same-day rolling-correlation peer shock after "
                "core-flow confirmation; this is the binding relation "
                "comparator, aggregate EV +0.3845 and PnL +$6,107.66."
            ),
            "exp-20260608-025": (
                "Same-industry characteristic peer shock failed; this avoids "
                "static industry similarity as the primary edge."
            ),
            "exp-20260608-028": (
                "Negative peer-shock resilience failed the accepted peer "
                "comparator; this tests positive lead-lag continuation instead."
            ),
            "exp-20260610-003": (
                "Industry leadership dispersion failed; this requires a "
                "ticker-pair lead-lag edge rather than group dispersion."
            ),
        },
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Numeric pass "
            "requires positive aggregate EV/PnL, no EV/PnL regression window, "
            "target sample >=20 across all 3 windows, survival >=5%, drawdown "
            "drift <=0.5pp, concentration guard, and beating exp-20260606-025 "
            "accepted peer-shock aggregate EV/PnL. Any positive result remains "
            "a replay lead until shared helper parity exists."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260610_022_rolling_lead_lag_peer_underreaction.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted" if numeric_passed else "rejected"
    )
    payload["accepted"] = False
    payload["accepted_alpha"] = False
    payload["production_accepted"] = False
    payload["interpretation"] = (
        "The lead-lag peer-underreaction source numerically cleared Gate 4 and "
        "beat the accepted peer-shock comparator, but it remains a replay-only "
        "lead because no shared daily helper was promoted."
        if numeric_passed
        else (
            "The lead-lag peer-underreaction source did not clear Gate 4 or "
            "did not beat the accepted peer-shock comparator; do not promote "
            "or locally retune this lead-lag relation family on frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if numeric_passed else "; ".join(payload["gate4"].get("numeric_failed_reasons", []))
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The simple lead-lag edge either did not add stable information "
            "beyond the accepted same-day correlation/core-flow relation, or "
            "its delayed reaction was too noisy after next-open execution and "
            "10-day costs. If it passes numerically, it still cannot be "
            "accepted until the same PIT field is shared with daily snapshots."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping lead-lag correlation, observation count, "
            "peer prior return, candidate prior-day lag, signal-day return, "
            "top-N, hold-day, cooldown, or paper notional on these windows."
        ),
        "new_evidence_required": (
            "Need supplier/customer/product-line/event-source relation "
            "provenance or closed forward replacement-value rows before "
            "revisiting lead-lag relation alpha."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Lead-lag days | Pairs | Trades |",
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
                days=scan.get("days_with_lead_lag_pairs", 0),
                pairs=scan.get("raw_lead_lag_pairs", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload.get("accepted_peer_shock_comparator") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Rolling Lead-Lag Peer Underreaction",
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
            "- Accepted peer-shock comparator EV/PnL: `{}` / `{}`".format(
                comparator.get("aggregate_ev_delta"),
                comparator.get("aggregate_pnl_delta"),
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"].get("numeric_failed_reasons", [])) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
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
        "accepted_alpha": False,
        "production_accepted": False,
        "numeric_gate4_passed": payload["gate4"]["numeric_passed"],
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
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
                "prior_peer_shock_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_prior_peer_shocks"
                ),
                "lead_lag_pair_count": payload["context_scan_by_window"][label].get(
                    "raw_lead_lag_pairs"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {
            **payload["calibration"],
            "actual_numeric_gate4_passed": payload["gate4"]["numeric_passed"],
            "actual_success": 1 if payload["gate4"]["numeric_passed"] else 0,
        },
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": payload["pre_run_questions"],
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any], log_record: dict[str, Any]
) -> None:
    result = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["numeric_passed"],
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
        "gate4_failed_reasons": payload["gate4"].get("numeric_failed_reasons", []),
        "calibration": log_record["calibration"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
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

    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


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
