"""exp-20260608-001: copper-growth stock leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: on CPER copper-demand thrust days, select up to two
liquid Materials / Industrials stock leaders as next-open, 10-trading-day
default-off paper candidates.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260606_029_sector_etf_lead_laggard_candidate_pool as base


EXPERIMENT_ID = "exp-20260608-001"
STEM = "copper_growth_stock_leadership"
TRIAL_FAMILY = "copper_growth_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "cper_thrust_materials_industrials_leadership_top2_10d_v1"
CHANGED_VARIABLE = "copper_growth_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

framework = base.framework
REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_001_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 2
SAME_TICKER_COOLDOWN_DAYS = 10

CONTEXT_TICKER = "CPER"
TARGET_SECTORS = {"Materials", "Industrials"}

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_CPER_SIGNAL_RETURN = 0.010
MIN_CPER_RELATIVE_VS_SPY = 0.008
MIN_CPER_CLOSE_LOCATION = 0.60
MIN_CPER_RET20_EXCESS_SPY = -0.020
MIN_CANDIDATE_SIGNAL_RETURN = 0.006
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.006
MIN_CANDIDATE_CLOSE_LOCATION = 0.65
MIN_CANDIDATE_VOLUME_RATIO = 0.90
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.005
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.030
MIN_CANDIDATE_RET5 = -0.030
MAX_CANDIDATE_RET5 = 0.150
MAX_CANDIDATE_REALIZED_VOL_20 = 0.085

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "commodity_move_already_priced",
        "sector_beta_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Copper is a different free OHLCV macro commodity proxy than rejected "
        "GLD/SLV producer lag and XLE sector beta; recent accepted relation "
        "alpha supports production-visible relations, but commodity-to-equity "
        "transfer has many failed neighbors."
    ),
    "recorded_at": "2026-06-08T00:05:49+00:00",
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
        "require a shared default-off adapter that computes the same CPER "
        "copper-thrust context, Materials/Industrials liquid stock leadership "
        "fields, same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, top-N limit, and concentration "
        "controls in both replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_LOAD_WINDOW_SNAPSHOT = base.BASE_LOAD_WINDOW_SNAPSHOT
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_GATE4 = base.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | {CONTEXT_TICKER},
    )


def _copper_context_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    cper_rows = snapshot.get(CONTEXT_TICKER) or []
    spy_rows = snapshot.get("SPY") or []
    cper_idx = indices.get(CONTEXT_TICKER, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if cper_idx is None or spy_idx is None or cper_idx < 20 or spy_idx < 20:
        return None
    cper_return = framework._daily_return(cper_rows, cper_idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    cper_ret20 = framework._ret(cper_rows, cper_idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    cper_close_location = framework._close_location(cper_rows[cper_idx])
    cper_volume_ratio = framework._volume_ratio(cper_rows, cper_idx) or 0.0
    if (
        cper_return is None
        or spy_return is None
        or cper_ret20 is None
        or spy_ret20 is None
        or cper_close_location is None
    ):
        return None
    cper_relative_vs_spy = cper_return - spy_return
    cper_ret20_excess_spy = cper_ret20 - spy_ret20
    if cper_return < MIN_CPER_SIGNAL_RETURN:
        return None
    if cper_relative_vs_spy < MIN_CPER_RELATIVE_VS_SPY:
        return None
    if cper_close_location < MIN_CPER_CLOSE_LOCATION:
        return None
    if cper_ret20_excess_spy < MIN_CPER_RET20_EXCESS_SPY:
        return None
    return {
        "date": signal_date,
        "context_ticker": CONTEXT_TICKER,
        "passed": True,
        "reason": "cper_copper_growth_thrust_passed",
        "cper_signal_day_return": round(cper_return, 6),
        "spy_signal_day_return": round(spy_return, 6),
        "cper_relative_vs_spy": round(cper_relative_vs_spy, 6),
        "cper_ret20": round(cper_ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "cper_ret20_excess_spy": round(cper_ret20_excess_spy, 6),
        "cper_close_location": round(cper_close_location, 6),
        "cper_volume_ratio_20d": round(cper_volume_ratio, 6),
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in {CONTEXT_TICKER, "SPY", "QQQ", "IWM"}:
        return None
    sector_meta = sector_entries.get(ticker) or {}
    if sector_meta.get("sector") not in TARGET_SECTORS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or idx + HOLD_DAYS >= len(rows):
        return None
    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    if signal_return is None or spy_return is None:
        return None
    relative_vs_spy = signal_return - spy_return
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None

    close_location = framework._close_location(row)
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx, 20)
    if (
        close_location is None
        or ret5 is None
        or ret20 is None
        or ret60 is None
        or spy_ret20 is None
        or spy_ret60 is None
        or realized_vol is None
    ):
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO:
        return None
    if ret5 < MIN_CANDIDATE_RET5 or ret5 > MAX_CANDIDATE_RET5:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None

    relative_vs_cper = signal_return - float(context["cper_signal_day_return"])
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        1.60 * float(context["cper_relative_vs_spy"])
        + 1.80 * relative_vs_spy
        + 0.65 * ret20_excess_spy
        + 0.30 * ret60_excess_spy
        + 0.35 * close_location
        + 0.035 * liquidity_score
        + 0.025 * min(volume_ratio, 3.0)
        - 0.45 * realized_vol
        - 0.12 * max(ret5, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "COPPER_GROWTH_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_cper": round(relative_vs_cper, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "copper_growth_context": context,
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
    stock_entries = {
        ticker: meta
        for ticker, meta in sector_entries.items()
        if meta.get("sector") in TARGET_SECTORS
    }
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "copper_growth_thrust_days": 0,
        "days_with_raw_copper_growth_candidates": 0,
        "raw_copper_growth_candidates": 0,
        "target_sector_count": len(stock_entries),
        "target_sectors": sorted(TARGET_SECTORS),
        "context_tickers": [CONTEXT_TICKER, "SPY"],
    }
    for signal_date in dates:
        context = _copper_context_for_day(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            continue
        context_scan["copper_growth_thrust_days"] += 1
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(stock_entries):
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=stock_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
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
            contexts.append({**context, "raw_candidate_count": 0})
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_relative_vs_spy"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        context_scan["days_with_raw_copper_growth_candidates"] += 1
        context_scan["raw_copper_growth_candidates"] += len(day_rows)
        contexts.append(
            {
                **context,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_relative_vs_spy": day_rows[0]["candidate_relative_vs_spy"],
                "top_candidate_ret20_excess_spy": day_rows[0][
                    "candidate_ret20_excess_spy"
                ],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_relative_vs_spy"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    return candidates, contexts, context_scan


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
        "positive_replay_lead_not_promoted_copper_growth_stock_leadership"
        if gate["passed"]
        else "rejected_copper_growth_stock_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "CPER copper-demand thrust may identify liquid Materials and "
                "Industrials stock leaders with next-open continuation as a "
                "distinct free-OHLCV commodity-growth relation."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "production_visible_free_ohlcv_copper_growth_relation",
            "nearby_prior_experiments": [
                "exp-20260607-011",
                "exp-20260606-029",
                "exp-20260428-035",
                "exp-20260504-045",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "copper_growth_contexts_by_window": payload["pressure_contexts_by_window"],
            "copper_growth_context_samples_by_window": payload[
                "pressure_context_samples_by_window"
            ],
            "negative_reflection": (
                "If rejected, the likely reason is that CPER commodity thrust "
                "is already priced into cyclical equities before the next open, "
                "or Materials/Industrials leadership is only broad sector beta. "
                "Do not retry by sweeping CPER return, close-location, target "
                "sectors, top-N, hold-day, cooldown, or notional thresholds on "
                "these frozen windows."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. A "
                "retry after rejection needs a materially new PIT relation, "
                "such as copper futures curve/warehouse inventory, producer "
                "revenue sensitivity, supply shock data, or closed forward "
                "replacement-value rows."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "context_ticker": CONTEXT_TICKER,
        "target_sectors": sorted(TARGET_SECTORS),
        "min_cper_signal_return": MIN_CPER_SIGNAL_RETURN,
        "min_cper_relative_vs_spy": MIN_CPER_RELATIVE_VS_SPY,
        "min_cper_close_location": MIN_CPER_CLOSE_LOCATION,
        "min_cper_ret20_excess_spy": MIN_CPER_RET20_EXCESS_SPY,
        "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
        "min_candidate_relative_vs_spy": MIN_CANDIDATE_RELATIVE_VS_SPY,
        "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
        "min_candidate_volume_ratio": MIN_CANDIDATE_VOLUME_RATIO,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
        "min_candidate_ret5": MIN_CANDIDATE_RET5,
        "max_candidate_ret5": MAX_CANDIDATE_RET5,
        "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].update(
        {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only CPER copper-growth stock leadership paper overlay"
            ),
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "copper_context_tickers": [CONTEXT_TICKER, "SPY"],
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on signal date. "
                "Paper entry is next available open with existing entry "
                "slippage; exit is the close 10 trading days after the signal "
                "with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: CPER copper-demand thrust may identify "
            "Materials/Industrials stock leaders before the next session fully "
            "reprices growth/infrastructure demand."
        ),
        "2_history_check": {
            "exp-20260607-011": (
                "GLD/SLV precious-metals producer lag failed because the ETF "
                "move looked priced into producers by next open. This run uses "
                "CPER and cyclical Materials/Industrials leaders, not precious "
                "metals producers or laggards."
            ),
            "exp-20260606-029": (
                "Sector ETF laggards failed as sector beta relabeling. This "
                "run uses a commodity-growth proxy and requires stock "
                "leadership rather than sector ETF lag."
            ),
            "exp-20260428-035/exp-20260504-045": (
                "Direct ETF/proxy expansion and XLE/USO pair confirmation were "
                "rejected; this run does not trade ETFs or alter core risk."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes. A positive replay still "
            "requires shared adapter parity before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_001_copper_growth_stock_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate2"]["runtime_fields"] = [
        "warehouse ohlcv Date/Open/High/Low/Close/Volume",
        "SPY daily OHLCV",
        "CPER daily OHLCV",
        "data/reference/broad_market_sector_map.json sector/status",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The copper-growth "
        "candidate source is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1 if payload["gate4"]["passed"] else 0,
        "actual_gate4_passed": payload["gate4"]["passed"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "failure_modes_observed": payload["gate4"]["failed_reasons"],
        "brier_score": round(
            (
                PREDICTION["success_probability"]
                - (1.0 if payload["gate4"]["passed"] else 0.0)
            )
            ** 2,
            6,
        ),
    }
    payload["interpretation"] = (
        "The CPER copper-growth stock-leadership source cleared Gate 4 as a "
        "replay-only/default-off lead. No production surface was promoted; a "
        "shared adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The CPER copper-growth stock-leadership source did not clear "
            "Gate 4; do not promote or locally retune this commodity-growth "
            "relation on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    old_thin_delta = payload["delta_metrics"]["by_window"]["old_thin"]
    target_count = payload["target_trade_summary"]["total_trade_count"]
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Gate 4 observed {count} target trades; old_thin changed by "
            "{ev:+.4f} EV and ${pnl:+,.2f}. If rejected, the after-cost "
            "next-open edge was either already priced by the signal close, "
            "too close to cyclical sector beta, or missing a more specific "
            "copper demand/supply relation."
        ).format(
            count=target_count,
            ev=old_thin_delta["expected_value_score"],
            pnl=old_thin_delta["total_pnl"],
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping CPER return, CPER close-location, "
            "CPER-vs-SPY spread, Materials/Industrials membership, stock "
            "leadership, volume, volatility, hold-day, top-N, cooldown, or "
            "paper notional on the same frozen windows."
        ),
        "new_evidence_required": (
            "A retry requires materially new PIT commodity-growth evidence "
            "such as copper futures curve, warehouse inventory, producer "
            "revenue sensitivity, supply shock data, or closed forward "
            "replacement-value rows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Copper days | Trades |",
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
                days=scan.get("copper_growth_thrust_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Copper-Growth Stock Leadership",
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
            "data/backtests/"
            "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
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
                "copper_growth_thrust_day_count": payload["context_scan_by_window"][
                    label
                ].get("copper_growth_thrust_days"),
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
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
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
    framework._load_window_snapshot = _load_window_snapshot
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
