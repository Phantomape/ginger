"""exp-20260608-023: sector peer gap-reaction transfer candidate pool.

Replay-only alpha search. This tests one fixed free-OHLCV relation:
same-sector stocks may drift after another liquid sector peer prints a
moderate gap-up plus volume shock, when the candidate has begun to follow but
has not chased the peer's full move.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260606_015_low_vol_20d_high_breakout_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-023"
STEM = "sector_peer_gap_reaction_transfer"
TRIAL_FAMILY = "sector_peer_gap_reaction_transfer_candidate_pool"
TRIAL_VARIANT_ID = "sector_peer_gap_reaction_transfer_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sector_peer_gap_volume_reaction_transfer_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_023_{STEM}.json"
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
MIN_SECTOR_MEMBER_COUNT = 6
MAX_SHOCK_PEERS_PER_SECTOR_DAY = 5
MIN_PEER_GAP_PCT = 0.03
MAX_PEER_GAP_PCT = 0.095
MIN_PEER_SIGNAL_RETURN = 0.015
MAX_PEER_SIGNAL_RETURN = 0.11
MIN_PEER_VOLUME_RATIO_20D = 1.35
MIN_PEER_CLOSE_LOCATION = 0.55
MIN_PEER_ADV20 = 75_000_000.0
MIN_PEER_RET20_EXCESS_SPY = -0.04

MIN_CANDIDATE_SIGNAL_RETURN = 0.0
MAX_CANDIDATE_SIGNAL_RETURN = 0.028
MIN_CANDIDATE_CLOSE_LOCATION = 0.42
MIN_CANDIDATE_VOLUME_RATIO_20D = 0.75
MAX_CANDIDATE_VOLUME_RATIO_20D = 2.80
MIN_CANDIDATE_RET5 = -0.045
MAX_CANDIDATE_RET5 = 0.065
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.055
MAX_CANDIDATE_RET20_EXCESS_SPY = 0.12
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.10
MAX_CANDIDATE_REALIZED_VOL_20D = 0.095

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

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
EXCLUDED_SECTORS = {"ETF", "Commodities", "Unknown", ""}

PREDICTION = {
    "success_probability": 0.21,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_sector_beta",
        "old_thin_regression",
        "drawdown_drift",
        "not_incremental_vs_accepted_peer_shock",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Prior read-only peer-reaction work found sector-level gap-volume "
        "peer shocks can carry excess-return information, and accepted "
        "rolling-corr peer shock validates relation alpha. Risk is that "
        "sector-level shocks are less specific than accepted correlation pairs "
        "and simply relabel beta."
    ),
    "recorded_at": "2026-06-08T19:05:20+00:00",
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
        "remain a replay lead unless a shared default-off adapter exposes the "
        "same sector peer gap-volume shock, same-sector candidate transfer, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, comparator, and concentration "
        "controls in both historical replay and daily production before any "
        "report queue, paper ledger, candidate priority, sizing, watchlist, or "
        "order surface could change."
    ),
}

BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_GATE4 = previous.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _gap_pct(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    open_price = framework._value(rows[idx], "Open")
    prior_close = framework._value(rows[idx - 1], "Close")
    if open_price is None or prior_close is None or prior_close <= 0:
        return None
    return open_price / prior_close - 1.0


def _sector_groups(
    sector_entries: dict[str, dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for ticker, meta in sector_entries.items():
        ticker = ticker.upper()
        if ticker in EXCLUDED_TICKERS or ticker not in snapshot:
            continue
        sector = str(meta.get("sector") or "")
        if sector in EXCLUDED_SECTORS:
            continue
        groups.setdefault(sector, []).append(ticker)
    return {
        sector: sorted(tickers)
        for sector, tickers in groups.items()
        if len(tickers) >= MIN_SECTOR_MEMBER_COUNT
    }


def _peer_shock_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_PEER_ADV20:
        return None

    gap = _gap_pct(rows, idx)
    signal_return = framework._daily_return(rows, idx)
    volume_ratio = framework._volume_ratio(rows, idx)
    close_location = framework._close_location(rows[idx])
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if any(
        value is None
        for value in [gap, signal_return, volume_ratio, close_location, ret20, spy_ret20]
    ):
        return None
    assert gap is not None
    assert signal_return is not None
    assert volume_ratio is not None
    assert close_location is not None
    assert ret20 is not None
    assert spy_ret20 is not None

    ret20_excess_spy = ret20 - spy_ret20
    if gap < MIN_PEER_GAP_PCT or gap > MAX_PEER_GAP_PCT:
        return None
    if signal_return < MIN_PEER_SIGNAL_RETURN or signal_return > MAX_PEER_SIGNAL_RETURN:
        return None
    if volume_ratio < MIN_PEER_VOLUME_RATIO_20D:
        return None
    if close_location < MIN_PEER_CLOSE_LOCATION:
        return None
    if ret20_excess_spy < MIN_PEER_RET20_EXCESS_SPY:
        return None

    score = (
        1.35 * gap
        + 1.10 * signal_return
        + 0.25 * min(volume_ratio, 4.0)
        + 0.35 * close_location
        + 0.35 * ret20_excess_spy
    )
    return {
        "ticker": ticker,
        "gap_pct": round(gap, 6),
        "signal_return": round(signal_return, 6),
        "volume_ratio_20d": round(volume_ratio, 6),
        "close_location": round(close_location, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "shock_score": round(score, 6),
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    sector: str,
    peer_shocks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    if any(
        value is None
        for value in [
            signal_return,
            close_location,
            volume_ratio,
            ret5,
            ret20,
            ret60,
            spy_ret20,
            spy_ret60,
            realized_vol20,
        ]
    ):
        return None
    assert signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
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
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if volume_ratio > MAX_CANDIDATE_VOLUME_RATIO_20D:
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

    best_peer = max(
        (row for row in peer_shocks if row["ticker"] != ticker),
        key=lambda row: (
            float(row["shock_score"]),
            float(row["signal_return"]),
            float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        ),
        default=None,
    )
    if best_peer is None:
        return None
    peer_count = sum(1 for row in peer_shocks if row["ticker"] != ticker)
    peer_score_sum = sum(float(row["shock_score"]) for row in peer_shocks if row["ticker"] != ticker)
    sector_meta = sector_entries[ticker]
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        1.25 * float(best_peer["shock_score"])
        + 0.45 * min(peer_score_sum, 2.0)
        + 0.70 * signal_return
        + 0.35 * close_location
        + 0.45 * ret20_excess_spy
        + 0.25 * ret60_excess_spy
        + 0.10 * min(volume_ratio, 2.5)
        + 0.04 * liquidity_score
        - 0.40 * abs(signal_return - 0.012)
        - 0.55 * realized_vol20
        - 0.25 * max(ret5, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SECTOR_PEER_GAP_REACTION_TRANSFER_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_return": round(signal_return, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "sector": sector,
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "peer_shock_count": peer_count,
        "peer_shock_score_sum": round(peer_score_sum, 6),
        "best_peer_ticker": best_peer["ticker"],
        "best_peer_gap_pct": best_peer["gap_pct"],
        "best_peer_signal_return": best_peer["signal_return"],
        "best_peer_volume_ratio_20d": best_peer["volume_ratio_20d"],
        "best_peer_close_location": best_peer["close_location"],
        "best_peer_ret20_excess_spy": best_peer["ret20_excess_spy"],
        "best_peer_shock_score": best_peer["shock_score"],
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
    sector_groups = _sector_groups(sector_entries, snapshot)
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "usable_sector_group_count": len(sector_groups),
        "days_with_sector_peer_shocks": 0,
        "days_with_raw_transfer_candidates": 0,
        "raw_sector_peer_shock_rows": 0,
        "raw_transfer_candidate_rows": 0,
    }
    for signal_date in dates:
        shocks_by_sector: dict[str, list[dict[str, Any]]] = {}
        for sector, tickers in sector_groups.items():
            sector_shocks = [
                row
                for ticker in tickers
                for row in [
                    _peer_shock_for_ticker(
                        snapshot=snapshot,
                        indices=indices,
                        ticker=ticker,
                        signal_date=signal_date,
                    )
                ]
                if row is not None
            ]
            if not sector_shocks:
                continue
            sector_shocks.sort(
                key=lambda row: (
                    -float(row["shock_score"]),
                    -float(row["signal_return"]),
                    -float(row["avg_dollar_volume_20d"]),
                    row["ticker"],
                )
            )
            shocks_by_sector[sector] = sector_shocks[:MAX_SHOCK_PEERS_PER_SECTOR_DAY]

        if not shocks_by_sector:
            continue
        scan["days_with_sector_peer_shocks"] += 1
        scan["raw_sector_peer_shock_rows"] += sum(
            len(rows) for rows in shocks_by_sector.values()
        )
        day_rows: list[dict[str, Any]] = []
        for sector, peer_shocks in shocks_by_sector.items():
            for ticker in sector_groups[sector]:
                row = _candidate_for_ticker(
                    snapshot=snapshot,
                    indices=indices,
                    sector_entries=sector_entries,
                    ticker=ticker,
                    signal_date=signal_date,
                    sector=sector,
                    peer_shocks=peer_shocks,
                )
                if row is None:
                    continue
                ab_entries = entries_by_date.get(signal_date, [])
                row["same_day_ab_entry_count"] = len(ab_entries)
                row["same_day_ab_overlap"] = bool(ab_entries)
                row["same_ticker_ab_overlap"] = any(
                    trade.get("ticker") == ticker for trade in ab_entries
                )
                day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["best_peer_shock_score"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_transfer_candidates"] += 1
        scan["raw_transfer_candidate_rows"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "rule_version": RULE_VERSION,
                "sector_peer_shock_sector_count": len(shocks_by_sector),
                "sector_peer_shock_count": sum(
                    len(rows) for rows in shocks_by_sector.values()
                ),
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_sector": top["sector"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_signal_return": top["candidate_signal_return"],
                "top_best_peer_ticker": top["best_peer_ticker"],
                "top_best_peer_shock_score": top["best_peer_shock_score"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["best_peer_shock_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_sector_member_count": MIN_SECTOR_MEMBER_COUNT,
            "max_shock_peers_per_sector_day": MAX_SHOCK_PEERS_PER_SECTOR_DAY,
            "min_peer_gap_pct": MIN_PEER_GAP_PCT,
            "max_peer_gap_pct": MAX_PEER_GAP_PCT,
            "min_peer_signal_return": MIN_PEER_SIGNAL_RETURN,
            "max_peer_signal_return": MAX_PEER_SIGNAL_RETURN,
            "min_peer_volume_ratio_20d": MIN_PEER_VOLUME_RATIO_20D,
            "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
            "max_candidate_volume_ratio_20d": MAX_CANDIDATE_VOLUME_RATIO_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
        }
    )
    return candidates, day_contexts, scan


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
        "positive_replay_lead_not_promoted_sector_peer_gap_reaction_transfer"
        if gate["passed"]
        else "rejected_sector_peer_gap_reaction_transfer_candidate_pool"
    )
    return gate


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


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Sector-level peer gap-volume shocks may identify liquid "
                "same-sector stocks with delayed follow-through when the "
                "candidate has begun to participate but has not chased the "
                "shock peer's full move."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_sector_peer_event_reaction_relation",
            "nearby_prior_experiments": [
                "exp-20260606-018",
                "exp-20260606-024",
                "exp-20260606-025",
                "exp-20260607-013",
                "exp-20260607-017",
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
                "If rejected, the likely reason is that sector-level peer "
                "gap-volume shocks are too broad and mostly relabel generic "
                "sector beta, whereas the accepted rolling-corr peer shock "
                "needs ticker-pair specificity plus core-flow confirmation. "
                "Do not answer by sweeping peer gap, volume, candidate return, "
                "top-N, hold-day, cooldown, or paper notional thresholds on "
                "these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry requires materially new PIT relation evidence such as "
                "customer/supplier links, characteristic-similarity peers, "
                "source-provenance event transfer, or closed forward "
                "replacement-value rows. Pure sector peer-shock threshold "
                "retunes should stay frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_sector_member_count": MIN_SECTOR_MEMBER_COUNT,
            "max_shock_peers_per_sector_day": MAX_SHOCK_PEERS_PER_SECTOR_DAY,
            "min_peer_gap_pct": MIN_PEER_GAP_PCT,
            "max_peer_gap_pct": MAX_PEER_GAP_PCT,
            "min_peer_signal_return": MIN_PEER_SIGNAL_RETURN,
            "max_peer_signal_return": MAX_PEER_SIGNAL_RETURN,
            "min_peer_volume_ratio_20d": MIN_PEER_VOLUME_RATIO_20D,
            "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
            "min_peer_avg_dollar_volume_20d": MIN_PEER_ADV20,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
            "max_candidate_volume_ratio_20d": MAX_CANDIDATE_VOLUME_RATIO_20D,
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "max_candidate_ret5": MAX_CANDIDATE_RET5,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: a same-sector peer's moderate gap+volume "
            "shock may be an early event-reaction signal for liquid peers that "
            "have started to participate but are not extended."
        ),
        "2_history_check": {
            "exp-20260606-018": (
                "Raw rolling-corr peer shock improved aggregate but failed "
                "old_thin/drawdown; ticker-pair relation alone was not enough."
            ),
            "exp-20260606-024/025": (
                "Core-flow confirmed rolling-corr peer shock passed and became "
                "the closest accepted comparator (+0.3845 EV, +$6,107.66, "
                "48 trades). This run must beat it before being considered a "
                "useful replay lead."
            ),
            "exp-20260607-013": (
                "Exact-industry earnings peer prewarm had only one trade; this "
                "run uses broader free OHLCV sector peer shocks to avoid that "
                "data scarcity."
            ),
            "exp-20260607-017": (
                "VBB-anchor correlation peer lag regressed EV/PnL and drawdown; "
                "this run does not anchor on accepted VBB rows or pair "
                "correlation."
            ),
        },
        "3_single_policy_bundle": (
            "Only one decision hypothesis is tested: sector peer gap-volume "
            "reaction transfer. Runner, comparator, artifact, log, card, "
            "ticket, and manifest only evaluate that fixed replay-only bundle."
        ),
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, concentration guard passes, and the accepted rolling-corr "
            "peer-shock comparator is beaten."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_023_sector_peer_gap_reaction_transfer.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The sector peer gap-reaction transfer source cleared the strict "
        "three-window replay and beat the accepted rolling-corr peer-shock "
        "comparator, but remains replay-only until a shared default-off adapter "
        "reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The sector peer gap-reaction transfer source did not clear Gate 4 "
            "or did not beat the accepted peer-shock comparator; do not promote "
            "or locally retune this sector peer-shock family on the frozen "
            "windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Sector-level peer shocks did not add enough ticker-specific "
            "relation information beyond broad sector beta. The accepted "
            "rolling-corr peer-shock route likely works because it combines "
            "ticker-pair specificity with core-flow confirmation; this broader "
            "sector route is easier to observe but less discriminating."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping sector peer gap, peer volume ratio, "
            "candidate signal return, close-location, ret5/ret20, top-N, "
            "hold-day, cooldown, or notional thresholds on these frozen windows."
        ),
        "new_evidence_required": (
            "Need materially new PIT relation provenance such as supplier/"
            "customer links, characteristic-similarity peers, source-family "
            "event transfer, or forward replacement-value rows before revisiting."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Shock days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("days_with_sector_peer_shocks", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload.get("accepted_peer_shock_comparator") or {}
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector Peer Gap-Reaction Transfer",
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
                "sector_peer_shock_day_count": payload["context_scan_by_window"][label].get(
                    "days_with_sector_peer_shocks"
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


def _update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8")) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
            },
        }
    )
    framework._write_json(TICKET_JSON, ticket)

    registry = (
        json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
        if REGISTRY_JSON.exists()
        else {"schema_version": 1, "experiments": []}
    )
    experiments = registry.setdefault("experiments", [])
    for row in experiments:
        if row.get("experiment_id") != EXPERIMENT_ID:
            continue
        row.update(
            {
                "status": payload["status"],
                "completed_at": payload["timestamp"],
                "updated_at": payload["timestamp"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "decision": payload["decision"],
                "aggregate_expected_value_delta": log_record[
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": log_record[
                    "aggregate_strategy_total_pnl_delta"
                ],
            }
        )
        break
    registry["updated_at"] = payload["timestamp"]
    REGISTRY_JSON.write_text(
        json.dumps(framework._safe(registry), ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
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


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)


def main() -> None:
    _patch_framework()
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
