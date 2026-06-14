"""exp-20260614-006: correlation-breakdown idiosyncratic leader scout.

Replay-only alpha search. It tests one free-OHLCV relation source: a stock
with a previously high-correlation same-industry peer basket breaks upward on
the signal day while that peer basket does not confirm. The hypothesis is that
the move is idiosyncratic demand/catalyst rather than generic industry beta.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260614-006"
STEM = "correlation_breakdown_idiosyncratic_leader"
TRIAL_FAMILY = "correlation_breakdown_idiosyncratic_leader_candidate_pool"
TRIAL_VARIANT_ID = "correlation_breakdown_idiosyncratic_leader_top1_next_open_10d_v1"
CHANGED_VARIABLE = "correlation_breakdown_idiosyncratic_leader_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_006_{STEM}.json"
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

CORR_LOOKBACK_DAYS = 60
MIN_CORR_OBSERVATIONS = 45
MIN_INDUSTRY_LIQUID_MEMBERS = 5
MIN_TOP_PEERS = 3
MAX_TOP_PEERS = 5
MIN_PEER_CORR = 0.35
MIN_AVG_TOP_PEER_CORR = 0.48

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.008
MAX_SIGNAL_RETURN = 0.080
MAX_PEER_BASKET_SIGNAL_RETURN = 0.004
MIN_SIGNAL_VS_PEER_BASKET = 0.018
MIN_SIGNAL_VS_SPY = 0.006
MIN_RET20_EXCESS_SPY = 0.000
MIN_RET60_EXCESS_SPY = -0.010
MIN_CLOSE_LOCATION = 0.58
MIN_VOLUME_RATIO_20D = 0.40
MAX_VOLUME_RATIO_20D = 3.50
MAX_REALIZED_VOL_20D = 0.105
MAX_TOP_PEER_POSITIVE_FRACTION = 0.67

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_RELATION_COMPARATORS = {
    "exp-20260607-008_industry_relative_laggard_repair": {
        "aggregate_expected_value_delta": 0.2763,
        "aggregate_pnl_delta": 6208.99,
        "note": "accepted shared industry-relative laggard repair adapter",
    },
    "exp-20260608-008_industry_stable_core_flow": {
        "aggregate_expected_value_delta": 0.1459,
        "aggregate_pnl_delta": 3731.54,
        "note": "accepted shared industry-stable core-flow adapter",
    },
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "generic_momentum_relabel",
        "peer_relation_noise",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_peer_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Accepted rolling-correlation peer shock shows relation alpha can work, "
        "but recent high-order and same-sector peer variants failed. This tests "
        "a different ex-ante field: upward decorrelation from a prior "
        "high-correlation same-industry basket with peer nonconfirmation."
    ),
    "recorded_at": "2026-06-14T04:06:03+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
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
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing OHLCV, peer context, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "same-industry peer basket, prior rolling-correlation filter, signal-day "
        "peer nonconfirmation, leader gates, same-ticker core-overlap exclusion, "
        "cooldown, next-open paper entry, 10-trading-day exit, costs, and "
        "concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: previously correlated industry peers that break upward "
        "while their high-correlation peer basket does not confirm may identify "
        "idiosyncratic demand, not generic industry beta."
    ),
    "2_history_check": {
        "exp-20260606-025": (
            "Accepted rolling-correlation peer-shock shared adapter shows a "
            "relation source can work when the relation itself is the edge."
        ),
        "exp-20260609-014": (
            "Rejected high-order same-day correlation cluster peer shock; this "
            "run does not require peer shock confirmation, it requires peer "
            "nonconfirmation after prior high correlation."
        ),
        "exp-20260610-022": (
            "Rejected simple rolling lead-lag underreaction; this run uses "
            "same-day upward decorrelation from a prior peer basket, not delayed "
            "follow-through."
        ),
        "exp-20260613-028": (
            "Rejected same-sector purity gate for peer shocks; this run uses "
            "same-industry peers but tests the opposite nonconfirmation field."
        ),
        "exp-20260613-027": (
            "Rejected weak-industry scarce leader; this run does not require a "
            "weak industry, only a previously correlated peer basket that fails "
            "to confirm the leader's signal-day move."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least 20 paper trades "
        "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and accepted relation comparators must be beaten. "
        "Replay-only positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_006_correlation_breakdown_idiosyncratic_leader.py"
    ),
}

ORIGINAL_GATE4 = framework._gate4
ORIGINAL_BUILD_PAYLOAD = framework._build_payload


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=100)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, framework._date_str(start), framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _industry_key(meta: dict[str, Any]) -> str:
    industry = str(meta.get("industry") or "").strip()
    sector = str(meta.get("sector") or "").strip()
    return industry or f"sector::{sector}"


def _industry_groups(
    sector_entries: dict[str, dict[str, Any]],
    available_tickers: set[str],
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for ticker, meta in sector_entries.items():
        if ticker not in available_tickers:
            continue
        key = _industry_key(meta)
        if not key or key == "sector::":
            continue
        groups.setdefault(key, []).append(ticker)
    return {
        key: sorted(tickers)
        for key, tickers in groups.items()
        if len(tickers) >= MIN_INDUSTRY_LIQUID_MEMBERS
    }


def _corr(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < MIN_CORR_OBSERVATIONS:
        return None
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    x_var = sum((value - x_mean) ** 2 for value in xs)
    y_var = sum((value - y_mean) ** 2 for value in ys)
    if x_var <= 1e-12 or y_var <= 1e-12:
        return None
    cov = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    return cov / math.sqrt(x_var * y_var)


def _prior_return_pairs(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    peer: str,
    signal_date: str,
) -> list[tuple[float, float]]:
    rows = snapshot.get(ticker) or []
    peer_rows = snapshot.get(peer) or []
    idx = indices.get(ticker, {}).get(signal_date)
    if idx is None or idx < CORR_LOOKBACK_DAYS + 1:
        return []
    pairs: list[tuple[float, float]] = []
    start = idx - CORR_LOOKBACK_DAYS
    for day_idx in range(start, idx):
        date_value = str(rows[day_idx].get("Date") or "")[:10]
        peer_idx = indices.get(peer, {}).get(date_value)
        if peer_idx is None or peer_idx < 1:
            continue
        stock_ret = framework._daily_return(rows, day_idx)
        peer_ret = framework._daily_return(peer_rows, peer_idx)
        if stock_ret is None or peer_ret is None:
            continue
        pairs.append((float(stock_ret), float(peer_ret)))
    return pairs


def _top_correlated_peers(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    peers: list[str],
    signal_date: str,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for peer in peers:
        if peer == ticker:
            continue
        pairs = _prior_return_pairs(
            snapshot=snapshot,
            indices=indices,
            ticker=ticker,
            peer=peer,
            signal_date=signal_date,
        )
        corr = _corr(pairs)
        if corr is None or corr < MIN_PEER_CORR:
            continue
        scored.append({"ticker": peer, "corr": corr, "observations": len(pairs)})
    scored.sort(key=lambda row: (-float(row["corr"]), str(row["ticker"])))
    return scored[:MAX_TOP_PEERS]


def _peer_signal_return(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    peer: str,
    signal_date: str,
) -> float | None:
    rows = snapshot.get(peer) or []
    idx = indices.get(peer, {}).get(signal_date)
    if idx is None or idx < 1:
        return None
    return framework._daily_return(rows, idx)


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    industry_group: list[str],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 80 or spy_idx < 80:
        return None
    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    top_peers = _top_correlated_peers(
        snapshot=snapshot,
        indices=indices,
        ticker=ticker,
        peers=industry_group,
        signal_date=signal_date,
    )
    if len(top_peers) < MIN_TOP_PEERS:
        return None
    top_peers = top_peers[:MIN_TOP_PEERS]
    avg_corr = sum(float(peer["corr"]) for peer in top_peers) / len(top_peers)
    if avg_corr < MIN_AVG_TOP_PEER_CORR:
        return None

    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    if None in (signal_return, spy_return, ret20, ret60, spy_ret20, spy_ret60):
        return None
    signal_return = float(signal_return)
    spy_return = float(spy_return)
    ret20_excess_spy = float(ret20) - float(spy_ret20)
    ret60_excess_spy = float(ret60) - float(spy_ret60)
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if signal_return - spy_return < MIN_SIGNAL_VS_SPY:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None

    peer_returns = [
        value
        for value in (
            _peer_signal_return(
                snapshot=snapshot,
                indices=indices,
                peer=str(peer["ticker"]),
                signal_date=signal_date,
            )
            for peer in top_peers
        )
        if value is not None
    ]
    if len(peer_returns) < MIN_TOP_PEERS:
        return None
    peer_basket_return = sum(float(value) for value in peer_returns) / len(peer_returns)
    peer_positive_fraction = sum(1 for value in peer_returns if float(value) > 0.0) / len(peer_returns)
    signal_vs_peer = signal_return - peer_basket_return
    if peer_basket_return > MAX_PEER_BASKET_SIGNAL_RETURN:
        return None
    if signal_vs_peer < MIN_SIGNAL_VS_PEER_BASKET:
        return None
    if peer_positive_fraction > MAX_TOP_PEER_POSITIVE_FRACTION:
        return None

    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    volume_ratio = framework._volume_ratio(rows, idx)
    if volume_ratio is None or volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    realized_vol = framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    score = (
        1.75 * signal_vs_peer
        + 0.85 * (signal_return - spy_return)
        + 0.55 * avg_corr
        + 0.45 * ret20_excess_spy
        + 0.20 * ret60_excess_spy
        + 0.18 * float(close_location)
        + 0.04 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.45 * float(realized_vol)
        - 0.20 * max(float(volume_ratio) - 2.25, 0.0)
        - 0.25 * max(signal_return - 0.050, 0.0)
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "CORRELATION_BREAKDOWN_IDIOSYNCRATIC_LEADER_PAPER",
        "candidate_score": round(score, 6),
        "signal_return": round(signal_return, 6),
        "spy_signal_return": round(spy_return, 6),
        "signal_vs_spy": round(signal_return - spy_return, 6),
        "peer_basket_signal_return": round(peer_basket_return, 6),
        "signal_vs_peer_basket": round(signal_vs_peer, 6),
        "top_peer_positive_fraction": round(peer_positive_fraction, 6),
        "top_peer_avg_corr_prior60": round(avg_corr, 6),
        "top_peers": [
            {
                "ticker": str(peer["ticker"]),
                "corr_prior60": round(float(peer["corr"]), 6),
                "observations": int(peer["observations"]),
            }
            for peer in top_peers
        ],
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret60_excess_spy": round(ret60_excess_spy, 6),
        "close_location": round(float(close_location), 6),
        "volume_ratio_20d": round(float(volume_ratio), 6),
        "avg_dollar_volume_20d": round(float(adv20), 2),
        "realized_vol_20d": round(float(realized_vol), 6),
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
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    industry_groups = _industry_groups(sector_entries, set(snapshot))
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "industry_group_count": len(industry_groups),
        "groups_with_candidate_days": 0,
        "candidate_rows_before_selection": 0,
        "rule_version": RULE_VERSION,
    }

    for signal_date in dates:
        date_candidate_count = 0
        for industry_key, tickers in industry_groups.items():
            group_count_before = len(candidates)
            for ticker in tickers:
                row = _candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    industry_group=tickers,
                    ticker=ticker,
                    signal_date=signal_date,
                )
                if row is None:
                    continue
                ab_entries = entries_by_date.get(signal_date, [])
                row["same_day_ab_entry_count"] = len(ab_entries)
                row["same_day_ab_overlap"] = bool(ab_entries)
                row["same_ticker_ab_overlap"] = any(
                    trade.get("ticker") == ticker for trade in ab_entries
                )
                row["industry_key"] = industry_key
                candidates.append(row)
            group_added = len(candidates) - group_count_before
            if group_added > 0:
                date_candidate_count += group_added
                contexts.append(
                    {
                        "date": signal_date,
                        "industry_key": industry_key,
                        "candidate_count": group_added,
                        "rule_version": RULE_VERSION,
                    }
                )
        if date_candidate_count > 0:
            scan["groups_with_candidate_days"] += 1
    scan["candidate_rows_before_selection"] = len(candidates)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["signal_vs_peer_basket"]),
            -float(row["top_peer_avg_corr_prior60"]),
            -float(row["avg_dollar_volume_20d"]),
            str(row.get("industry_key") or ""),
            row["ticker"],
        )
    )
    return candidates, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    best_ev = max(
        item["aggregate_expected_value_delta"]
        for item in ACCEPTED_RELATION_COMPARATORS.values()
    )
    best_pnl = max(item["aggregate_pnl_delta"] for item in ACCEPTED_RELATION_COMPARATORS.values())
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= best_ev:
        failed.append("accepted_relation_ev_not_beaten")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= best_pnl:
        failed.append("accepted_relation_pnl_not_beaten")
    gate["accepted_relation_comparators"] = ACCEPTED_RELATION_COMPARATORS
    gate["failed_reasons"] = list(dict.fromkeys(failed))
    gate["passed"] = not gate["failed_reasons"]
    gate["decision"] = (
        "positive_replay_lead_not_promoted_correlation_breakdown_idiosyncratic_leader"
        if gate["passed"]
        else "rejected_correlation_breakdown_idiosyncratic_leader_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    aggregate = payload["delta_metrics"]["aggregate"]
    reflection = {
        "why_result_happened": (
            "The prior-correlation/nonconfirmation field found enough "
            "replacement value to clear the replay gate, but it remains only a "
            "lead because there is no shared daily/backtest helper."
            if passed
            else (
                "The prior-correlation/nonconfirmation field did not clear "
                "Gate 4. The likely reason is that same-industry decorrelation "
                "still relabels short-horizon momentum or noisy peer baskets; "
                "it did not beat accepted relation comparators after next-open "
                "execution, costs, cooldown, drawdown, and concentration checks."
            )
        ),
        "realized_failure_mode": (
            "none_numeric_gate4_passed"
            if passed
            else "generic_momentum_or_peer_relation_noise"
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping correlation lookback, peer count, "
            "correlation threshold, peer nonconfirmation threshold, volume, "
            "hold-day, cooldown, top-N, or notional on these frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs a materially richer PIT relation or flow field, "
            "such as options/borrow/ownership confirmation, timestamped event "
            "relation provenance, or closed forward replacement rows from a "
            "shared daily helper."
        ),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": status,
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "mechanism_family": "production_visible_free_ohlcv_relation_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260606-025",
                "exp-20260609-014",
                "exp-20260610-022",
                "exp-20260613-028",
                "exp-20260613-027",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_free_ohlcv_correlation_breakdown_peer_nonconfirmation_field",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "accepted_comparators": ACCEPTED_RELATION_COMPARATORS,
            "post_run_reflection": reflection,
            "negative_reflection": None if passed else reflection["why_result_happened"],
            "next_evidence_needed": reflection["new_evidence_required"],
            "correlation_breakdown_contexts_by_window": payload["pressure_contexts_by_window"],
            "correlation_breakdown_scan_by_window": payload["context_scan_by_window"],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The correlation-breakdown idiosyncratic-leader source passed "
                "as a replay-only lead, but no production surface changed and "
                "a shared default-off parity adapter is required before use."
                if passed
                else (
                    "The correlation-breakdown idiosyncratic-leader source was "
                    "rejected; it did not establish a distinct relation edge "
                    "under the standard three-window protocol."
                )
            ),
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "correlation_lookback_days": CORR_LOOKBACK_DAYS,
        "min_correlation_observations": MIN_CORR_OBSERVATIONS,
        "min_industry_liquid_members": MIN_INDUSTRY_LIQUID_MEMBERS,
        "min_top_peers": MIN_TOP_PEERS,
        "max_top_peers": MAX_TOP_PEERS,
        "min_peer_corr": MIN_PEER_CORR,
        "min_avg_top_peer_corr": MIN_AVG_TOP_PEER_CORR,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "max_peer_basket_signal_return": MAX_PEER_BASKET_SIGNAL_RETURN,
        "min_signal_vs_peer_basket": MIN_SIGNAL_VS_PEER_BASKET,
        "min_signal_vs_spy": MIN_SIGNAL_VS_SPY,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
    }
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Correlation-Breakdown Idiosyncratic Leader",
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
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
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
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
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
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": framework._repo_rel(OUT_JSON),
        "log": framework._repo_rel(LOG_JSON),
        "card": framework._repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": ACCEPTED_RELATION_COMPARATORS,
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
                "pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": framework._repo_rel(OUT_JSON),
                "log": framework._repo_rel(LOG_JSON),
                "card": framework._repo_rel(CARD_MD),
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
                "accepted": False,
                "numeric_gate4_passed": bool(payload["gate4"]["passed"]),
                "gate4": payload["gate4"],
                "calibration": payload["calibration"],
                "production_impact": PRODUCTION_IMPACT,
                "post_run_reflection": payload["post_run_reflection"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)

    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": bool(payload["gate4"]["passed"]),
        "artifact": framework._repo_rel(OUT_JSON),
        "log": framework._repo_rel(LOG_JSON),
        "card": framework._repo_rel(CARD_MD),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
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
        "artifact": framework._repo_rel(OUT_JSON),
        "log": framework._repo_rel(LOG_JSON),
        "ticket_file": framework._repo_rel(TICKET_JSON),
        "card_file": framework._repo_rel(CARD_MD),
        "revision_manifest_file": framework._repo_rel(MANIFEST_JSON),
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
    framework._load_window_snapshot = _load_window_snapshot
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._configure_sleeve_globals()


def main() -> None:
    _patch_framework()
    framework.main()


if __name__ == "__main__":
    main()
