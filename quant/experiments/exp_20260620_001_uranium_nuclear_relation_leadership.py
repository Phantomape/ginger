"""exp-20260620-001: uranium producer to nuclear relation leadership scout.

Replay-only alpha search. The single decision hypothesis is that PIT OHLCV
leadership in uranium producers (CCJ/LEU/NXE) can identify nuclear demand or
supply shocks that spill into liquid nuclear power, reactor, and equipment
stocks over the next 10 trading days.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


framework = base.framework

EXPERIMENT_ID = "exp-20260620-001"
STEM = "uranium_nuclear_relation_leadership"
TRIAL_FAMILY = "uranium_nuclear_relation_leadership_candidate_pool"
TRIAL_VARIANT_ID = "uranium_nuclear_top1_next_open_10d_v1"
CHANGED_VARIABLE = "uranium_producer_to_nuclear_power_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = base.REPO_ROOT
BASELINE_RESULT_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_001_{STEM}.json"
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

MARKET_PROXY_TICKER = "SPY"
URANIUM_ANCHOR_TICKERS = ("CCJ", "LEU", "NXE")
NUCLEAR_CANDIDATE_TICKERS = ("BWXT", "CEG", "NNE", "OKLO", "SMR", "TLN", "VST")

MIN_ANCHOR_COUNT = 2
MIN_ANCHOR_RET20_EXCESS_SPY = 0.04
MIN_ANCHOR_RET5 = -0.03
MIN_ANCHOR_CLOSE_LOCATION = 0.45
MIN_ANCHOR_AVG_DOLLAR_VOLUME_20D = 25_000_000.0
MIN_SPY_RET20 = -0.08

MIN_PRICE = 8.0
MIN_AVG_DOLLAR_VOLUME_20D = 25_000_000.0
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.02
MIN_CANDIDATE_RET5 = -0.04
MIN_CANDIDATE_CLOSE_LOCATION = 0.45
MIN_SIGNAL_RETURN = -0.06
MAX_SIGNAL_RETURN = 0.12
MAX_REALIZED_VOL_20D = 0.16

COMPRESSION_COMPARATOR = base.COMPRESSION_COMPARATOR
DISTRIBUTION_COMPARATOR = base.DISTRIBUTION_COMPARATOR

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "theme_beta_not_incremental",
        "window_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "thin_sample_or_concentration",
    ],
    "confidence_reason": (
        "Prior GLD/SLV producer-lag and copper/growth relation scouts failed, "
        "but this tests a distinct uranium/nuclear relation with broad PIT "
        "OHLCV warehouse coverage and no SEC/LLM dependency. Main risk is "
        "that it collapses into generic volatile theme beta after next-open "
        "execution and costs."
    ),
    "recorded_at": "2026-06-20T00:08:03+00:00",
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
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "uses_uranium_nuclear_relation": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $8 and ADV20 >= $25M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": (
            "missing anchor/candidate OHLCV, failed uranium anchor breadth, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "uranium anchor breadth, fixed nuclear candidate universe, liquid "
        "constructive candidate gates, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT OHLCV leadership in uranium producers "
        "(CCJ/LEU/NXE) may identify demand/supply shocks that spill into "
        "liquid nuclear power, small-reactor, and nuclear equipment stocks "
        "over the next 10 trading days."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Novelty gate warned on generic OHLCV leadership families. The "
            "override declares a new evidence axis: uranium producer anchors "
            "to a fixed nuclear power/equipment universe, not GLD/SLV producer "
            "lag, copper-growth, rate-relief growth, broad leadership, or AI "
            "power fixed universe."
        ),
        "exp-20260607-011": (
            "Rejected precious metals ETF / producer lag. This run does not "
            "use GLD/SLV or precious-metals miners; it uses uranium producer "
            "breadth as the anchor and nuclear utilities/reactor/equipment "
            "stocks as the candidate universe."
        ),
        "exp-20260608-001": (
            "Rejected copper/cyclical relation work; this run is a distinct "
            "nuclear supply/demand theme and fixed ticker set."
        ),
        "exp-20260619-021": (
            "Rejected TLT rate-relief growth leadership. This run does not use "
            "macro duration proxies or QQQ-vs-SPY growth context."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two "
        "EV-improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and the "
        "accepted compression/distribution candidate-pool comparators must be "
        "beaten. Replay-only positives are leads until shared daily/backtest "
        "parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_001_uranium_nuclear_relation_leadership.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return framework._round(value, digits)


def _configure_framework() -> None:
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
    framework.MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._configure_sleeve_globals()


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = framework._parse_date(cfg["start"]) - timedelta(days=130)
    end = framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(
        set(eligible_tickers)
        | {MARKET_PROXY_TICKER}
        | set(URANIUM_ANCHOR_TICKERS)
        | set(NUCLEAR_CANDIDATE_TICKERS)
    )
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


def _anchor_context(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = framework.shadow._series(snapshot, MARKET_PROXY_TICKER)
    spy_idx = indices.get(MARKET_PROXY_TICKER, {}).get(signal_date)
    if spy_idx is None or spy_idx < 60:
        return None
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if spy_ret20 is None or spy_ret20 < MIN_SPY_RET20:
        return None

    passed: list[dict[str, Any]] = []
    for ticker in URANIUM_ANCHOR_TICKERS:
        rows = framework.shadow._series(snapshot, ticker)
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 60:
            continue
        ret20 = framework._ret(rows, idx, 20)
        ret5 = framework._ret(rows, idx, 5)
        close_location = framework._close_location(rows[idx])
        adv20 = framework._avg_dollar_volume(rows, idx)
        signal_return = framework._daily_return(rows, idx)
        if any(value is None for value in (ret20, ret5, close_location, adv20, signal_return)):
            continue
        assert ret20 is not None and ret5 is not None
        assert close_location is not None and adv20 is not None and signal_return is not None
        ret20_excess_spy = ret20 - spy_ret20
        if ret20_excess_spy < MIN_ANCHOR_RET20_EXCESS_SPY:
            continue
        if ret5 < MIN_ANCHOR_RET5:
            continue
        if close_location < MIN_ANCHOR_CLOSE_LOCATION:
            continue
        if adv20 < MIN_ANCHOR_AVG_DOLLAR_VOLUME_20D:
            continue
        passed.append(
            {
                "ticker": ticker,
                "ret20": _round(ret20, 6),
                "ret5": _round(ret5, 6),
                "ret20_excess_spy": _round(ret20_excess_spy, 6),
                "signal_return": _round(signal_return, 6),
                "close_location": _round(close_location, 6),
                "avg_dollar_volume_20d": _round(adv20, 2),
            }
        )

    if len(passed) < MIN_ANCHOR_COUNT:
        return None
    avg_ret20_excess = sum(float(row["ret20_excess_spy"]) for row in passed) / len(passed)
    avg_ret5 = sum(float(row["ret5"]) for row in passed) / len(passed)
    best_ret20_excess = max(float(row["ret20_excess_spy"]) for row in passed)
    return {
        "anchor_tickers": list(URANIUM_ANCHOR_TICKERS),
        "passed_anchor_tickers": [row["ticker"] for row in passed],
        "passed_anchor_count": len(passed),
        "spy_ret20": _round(spy_ret20, 6),
        "anchor_avg_ret20_excess_spy": _round(avg_ret20_excess, 6),
        "anchor_best_ret20_excess_spy": _round(best_ret20_excess, 6),
        "anchor_avg_ret5": _round(avg_ret5, 6),
        "anchor_details": passed,
        "anchor_context_known_at": "signal_date_ohlcv_close",
    }


def _candidate_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, MARKET_PROXY_TICKER)
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get(MARKET_PROXY_TICKER, {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if min(idx, spy_idx) < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    close_location = framework._close_location(rows[idx])
    ret20 = framework._ret(rows, idx, 20)
    ret5 = framework._ret(rows, idx, 5)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    realized_vol = framework._realized_vol(rows, idx, 20)
    required = (signal_return, close_location, ret20, ret5, spy_ret20, realized_vol)
    if any(value is None for value in required):
        return None
    assert signal_return is not None and close_location is not None
    assert ret20 is not None and ret5 is not None and spy_ret20 is not None
    assert realized_vol is not None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if realized_vol > MAX_REALIZED_VOL_20D:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret5 < MIN_CANDIDATE_RET5:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    score = (
        0.75 * ret20_excess_spy
        + 0.45 * ret5
        + 0.35 * float(context["anchor_avg_ret20_excess_spy"])
        + 0.20 * float(context["anchor_avg_ret5"])
        + 0.12 * close_location
        - 0.25 * realized_vol
        + 0.025 * math.log10(max(adv20, 1.0) / 1_000_000.0)
    )
    return {
        "candidate_score": _round(score, 6),
        "candidate_signal_return": _round(signal_return, 6),
        "candidate_close_location": _round(close_location, 6),
        "candidate_ret20": _round(ret20, 6),
        "candidate_ret5": _round(ret5, 6),
        "candidate_ret20_excess_spy": _round(ret20_excess_spy, 6),
        "candidate_avg_dollar_volume_20d": _round(adv20, 2),
        "candidate_volume_ratio_20d": _round(volume_ratio, 6),
        "candidate_realized_vol_20d": _round(realized_vol, 6),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(NUCLEAR_CANDIDATE_TICKERS) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["fixed_candidate_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    context_sample: list[dict[str, Any]] = []
    for signal_date in window_dates:
        context = _anchor_context(snapshot=snapshot, indices=indices, signal_date=signal_date)
        if context is None:
            scan["failed_anchor_context_days"] += 1
            continue
        scan["anchor_context_pass_days"] += 1
        if len(context_sample) < 5:
            context_sample.append({"date": signal_date, **context})
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            confirm = _candidate_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if confirm is None:
                scan["failed_candidate_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "URANIUM_NUCLEAR_RELATION_LEADERSHIP_PAPER",
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "signal_date_ohlcv_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "same_ticker_ab_overlap": False,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **context,
                    **confirm,
                }
            )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_ret5"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(candidates)
    scan["candidate_signal_days"] = len({row["date"] for row in candidates})
    scan["candidate_tickers"] = len({row["ticker"] for row in candidates})
    scan["context_sample"] = context_sample
    return candidates, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "anchor_tickers": list(URANIUM_ANCHOR_TICKERS),
        "candidate_tickers": list(NUCLEAR_CANDIDATE_TICKERS),
        "min_anchor_count": MIN_ANCHOR_COUNT,
        "min_anchor_ret20_excess_spy": MIN_ANCHOR_RET20_EXCESS_SPY,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_uranium_nuclear_relation_leadership"
        if gate["passed"]
        else "rejected_uranium_nuclear_relation_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    _configure_framework()
    timestamp = _utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()

    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    context_scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and uranium/nuclear relation replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = _load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(universe),
        )
        sector_entries = {
            ticker: meta for ticker, meta in sector_entries_all.items() if ticker in snapshot
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
            "market_proxy_present": MARKET_PROXY_TICKER in snapshot,
            "anchors_present": {
                ticker: ticker in snapshot for ticker in URANIUM_ANCHOR_TICKERS
            },
            "candidates_present": {
                ticker: ticker in snapshot for ticker in NUCLEAR_CANDIDATE_TICKERS
            },
        }
        candidates, context_scan = _candidate_rows_for_window(
            snapshot=snapshot,
            cfg=cfg,
            sector_entries=sector_entries,
        )
        selected_trades, filtered_candidates = framework._select_paper_trades(
            snapshot=snapshot,
            candidates=candidates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected_trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]
        raw_candidate_counts[label] = len(candidates)
        context_scan_by_window[label] = context_scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_candidate_count": len(candidates),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    rejection_reason = None if gate4["passed"] else "; ".join(gate4["failed_reasons"])
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_replay_scout",
        "implementation_mode": "private_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_uranium_nuclear_candidate_pool",
        "new_evidence_type": "free_ohlcv_uranium_producer_to_nuclear_relation",
        "nearby_prior_experiments": [
            "exp-20260607-011",
            "exp-20260608-001",
            "exp-20260501-008",
            "exp-20260619-021",
        ],
        "prior_trial_count": 0,
        "multiple_testing_risk_bucket": "high",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "anchor_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Uranium anchor and candidate stock features are computed from "
                "OHLCV rows with Date <= signal_date. Paper entry is the next "
                "available open with existing entry slippage; exit is the close "
                "10 trading days after the signal with target-side sell slippage "
                "and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "anchor_tickers": list(URANIUM_ANCHOR_TICKERS),
            "candidate_tickers": list(NUCLEAR_CANDIDATE_TICKERS),
            "min_anchor_count": MIN_ANCHOR_COUNT,
            "min_anchor_ret20_excess_spy": MIN_ANCHOR_RET20_EXCESS_SPY,
            "min_anchor_ret5": MIN_ANCHOR_RET5,
            "min_anchor_close_location": MIN_ANCHOR_CLOSE_LOCATION,
            "min_spy_ret20": MIN_SPY_RET20,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret5": MIN_CANDIDATE_RET5,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": _repo_rel(BASELINE_RESULT_JSON),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "uranium anchor OHLCV Date/Open/High/Low/Close/Volume",
                "nuclear candidate OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV Date/Open/High/Low/Close/Volume",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "survival_rate_by_window": {
                label: before_metrics[label].get("survival_rate") for label in before_metrics
            },
            "passed": min_survival >= 0.05,
            "note": (
                "No new core filter or entry rule was added. The candidate "
                "source is additive default-off paper, so core signals "
                "generated/survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "raw_candidate_counts": raw_candidate_counts,
        "context_scan_by_window": context_scan_by_window,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "interpretation": (
            "The uranium/nuclear relation source cleared Gate 4 as a "
            "replay-only/default-off lead, but no production surface was "
            "promoted."
            if gate4["passed"]
            else (
                "The uranium/nuclear relation source did not clear Gate 4 "
                "(failed: "
                + (", ".join(gate4["failed_reasons"]) or "none")
                + "). Do not promote or tune this fixed relation bundle on "
                "the same frozen windows."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "A retry needs materially different PIT nuclear demand/supply "
            "evidence, such as contract awards, utility procurement, reactor "
            "approval events, ownership/flow confirmation, or closed forward "
            "replacement rows. Do not sweep anchor lookbacks, candidate "
            "thresholds, top-N, hold, cooldown, or notional on these frozen "
            "windows."
        ),
        "post_run_reflection": {
            "why_result_happened": (
                "Gate 4 passed numerically, but this is replay-only because no "
                "shared daily/backtest helper exists."
                if gate4["passed"]
                else (
                    "Rejected. Uranium anchor breadth plus fixed nuclear "
                    "candidate leadership did not add robust replacement value "
                    "versus the accepted compression/distribution candidate-"
                    "pool comparators after next-open execution, costs, "
                    "cooldown, and concentration checks (failed: {}). The "
                    "relation likely relabels a crowded volatile nuclear theme "
                    "rather than a distinct spillover edge."
                ).format(", ".join(gate4["failed_reasons"]) or "none")
            ),
            "outcome_summary": (
                "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
                "max drawdown drift {:+.4f}; {} paper trades.".format(
                    aggregate["expected_value_score_delta_sum"],
                    aggregate["total_pnl_delta_sum"],
                    float(aggregate["max_drawdown_delta_max"] or 0.0),
                    target_summary["total_trade_count"],
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping uranium anchor count/ret20/ret5/"
                "close-location thresholds, fixed candidate list, RS/volume/"
                "vol guards, top-N, hold days, cooldown, or notional on these "
                "frozen windows."
            ),
            "new_evidence_required": (
                "Need PIT event/procurement/flow/ownership evidence or closed "
                "forward replacement-value rows before revisiting uranium to "
                "nuclear relation leadership."
            ),
        },
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Anchor days | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {anchor} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                anchor=scan.get("anchor_context_pass_days", 0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Uranium Nuclear Relation Leadership",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(BASELINE_RESULT_JSON),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "anchor_context_pass_days": payload["context_scan_by_window"][label].get("anchor_context_pass_days"),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
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


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
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
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
