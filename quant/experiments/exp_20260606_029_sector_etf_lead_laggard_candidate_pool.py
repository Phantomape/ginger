"""exp-20260606-029: sector ETF lead / same-sector laggard candidate pool.

Replay-only alpha search. This tests one production-visible free-OHLCV relation
source: when XLE/XLP/XLU/XLV lead SPY and close firm, admit one liquid
same-sector stock that has begun reacting but still lags its sector ETF.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260606-029"
STEM = "sector_etf_lead_laggard_candidate_pool"
TRIAL_FAMILY = "sector_etf_lead_laggard_candidate_pool"
TRIAL_VARIANT_ID = "defensive_energy_sector_etf_lead_laggard_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sector_etf_lead_same_sector_laggard_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_029_{STEM}.json"
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

SECTOR_ETF_BY_SECTOR = {
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Consumer Defensive": "XLP",
    "Utilities": "XLU",
}
SECTOR_ETF_TICKERS = set(SECTOR_ETF_BY_SECTOR.values())

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_ETF_SIGNAL_RETURN = 0.004
MIN_ETF_RELATIVE_VS_SPY = 0.003
MIN_ETF_CLOSE_LOCATION = 0.55
MIN_ETF_RET20_EXCESS_SPY = -0.02
MIN_CANDIDATE_SIGNAL_RETURN = 0.0
MAX_CANDIDATE_RELATIVE_VS_ETF = 0.003
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.015
MIN_CANDIDATE_CLOSE_LOCATION = 0.55
MAX_CANDIDATE_RET5 = 0.12
MAX_CANDIDATE_REALIZED_VOL_20 = 0.085

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "sector_etf_relabeling",
        "concentration_failed",
        "target_sample_too_small",
    ],
    "confidence_reason": (
        "Sector ETF direct expansion failed, but using XLE/XLP/XLU/XLV as "
        "non-traded relation context for same-sector stock laggards is a "
        "different production-visible free-OHLCV candidate source; recent "
        "accepted peer-shock evidence supports relation-aware sources."
    ),
    "recorded_at": "2026-06-06T23:06:17+00:00",
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
        "require a shared default-off adapter that computes the same sector "
        "ETF relation fields, same-sector liquid stock laggard gates, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, and concentration controls in "
        "both replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_LOAD_WINDOW_SNAPSHOT = framework._load_window_snapshot
BASE_BUILD_PAYLOAD = framework._build_payload
BASE_GATE4 = framework._gate4
BASE_PERSIST = framework.persist


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | SECTOR_ETF_TICKERS,
    )


def _sector_etf_contexts_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> list[dict[str, Any]]:
    spy_rows = snapshot.get("SPY") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if spy_idx is None or spy_idx < 20:
        return []
    spy_return = framework._daily_return(spy_rows, spy_idx)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if spy_return is None or spy_ret20 is None:
        return []

    contexts: list[dict[str, Any]] = []
    for sector, etf in SECTOR_ETF_BY_SECTOR.items():
        rows = snapshot.get(etf) or []
        idx = indices.get(etf, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        etf_return = framework._daily_return(rows, idx)
        etf_ret20 = framework._ret(rows, idx, 20)
        etf_close_location = framework._close_location(rows[idx])
        etf_volume_ratio = framework._volume_ratio(rows, idx) or 0.0
        if etf_return is None or etf_ret20 is None or etf_close_location is None:
            continue
        etf_relative_vs_spy = etf_return - spy_return
        etf_ret20_excess_spy = etf_ret20 - spy_ret20
        passed = (
            etf_return >= MIN_ETF_SIGNAL_RETURN
            and etf_relative_vs_spy >= MIN_ETF_RELATIVE_VS_SPY
            and etf_close_location >= MIN_ETF_CLOSE_LOCATION
            and etf_ret20_excess_spy >= MIN_ETF_RET20_EXCESS_SPY
        )
        if not passed:
            continue
        contexts.append(
            {
                "date": signal_date,
                "sector": sector,
                "sector_etf_ticker": etf,
                "passed": True,
                "reason": "sector_etf_lead_passed",
                "sector_etf_signal_day_return": round(etf_return, 6),
                "spy_signal_day_return": round(spy_return, 6),
                "sector_etf_relative_vs_spy": round(etf_relative_vs_spy, 6),
                "sector_etf_ret20": round(etf_ret20, 6),
                "spy_ret20": round(spy_ret20, 6),
                "sector_etf_ret20_excess_spy": round(etf_ret20_excess_spy, 6),
                "sector_etf_close_location": round(etf_close_location, 6),
                "sector_etf_volume_ratio_20d": round(etf_volume_ratio, 6),
                "rule_version": RULE_VERSION,
            }
        )
    return contexts


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in SECTOR_ETF_TICKERS:
        return None
    sector_meta = sector_entries.get(ticker) or {}
    if sector_meta.get("sector") != context["sector"]:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 20 or spy_idx < 20 or idx + HOLD_DAYS >= len(rows):
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
    candidate_relative_vs_etf = (
        signal_return - float(context["sector_etf_signal_day_return"])
    )
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if candidate_relative_vs_etf > MAX_CANDIDATE_RELATIVE_VS_ETF:
        return None
    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    realized_vol = framework._realized_vol(rows, idx)
    if ret5 is None or ret20 is None or spy_ret20 is None or realized_vol is None:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    relative_vs_spy = signal_return - spy_return
    lag_gap = max(0.0, -candidate_relative_vs_etf)
    score = (
        1.40 * float(context["sector_etf_relative_vs_spy"])
        + 1.00 * lag_gap
        + 0.45 * ret20_excess_spy
        + 0.30 * close_location
        + 0.035 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.50 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "SECTOR_ETF_LEAD_LAGGARD_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_sector_etf": round(candidate_relative_vs_etf, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "sector_etf_context": context,
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
        if meta.get("sector") in SECTOR_ETF_BY_SECTOR
    }
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "sector_etf_lead_contexts": 0,
        "sector_etf_lead_days": 0,
        "sector_etf_context_by_sector": {},
        "candidate_sector_count": len(stock_entries),
        "sector_etfs_used": sorted(SECTOR_ETF_TICKERS),
    }
    lead_dates: set[str] = set()
    sector_counts: dict[str, int] = {}
    for signal_date in dates:
        day_contexts = _sector_etf_contexts_for_day(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if not day_contexts:
            continue
        lead_dates.add(signal_date)
        for context in day_contexts:
            contexts.append(context)
            sector_counts[context["sector"]] = sector_counts.get(context["sector"], 0) + 1
            for ticker in stock_entries:
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
                candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    context_scan["sector_etf_lead_contexts"] = len(contexts)
    context_scan["sector_etf_lead_days"] = len(lead_dates)
    context_scan["sector_etf_context_by_sector"] = sector_counts
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
        "positive_replay_lead_not_promoted_sector_etf_laggard_candidate_pool"
        if gate["passed"]
        else "rejected_sector_etf_laggard_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Defensive and energy sector ETF leadership may identify "
                "same-sector liquid stock laggards with next-open continuation "
                "when the ETF leads SPY but the stock has only begun to react."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "production_visible_free_ohlcv_sector_etf_to_stock_relation",
            "nearby_prior_experiments": [
                "exp-20260430-008",
                "exp-20260515-017",
                "exp-20260511-024",
                "exp-20260606-024",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "sector_etf_contexts_by_window": payload["pressure_contexts_by_window"],
            "sector_etf_context_samples_by_window": payload[
                "pressure_context_samples_by_window"
            ],
            "negative_reflection": (
                "If rejected, the likely reason is that defensive/energy sector "
                "ETF leadership is either too sparse, duplicates generic "
                "defensive rotation, or lacks enough single-name catch-up "
                "replacement value. Do not retry by changing ETF-return, "
                "laggard, hold-day, cooldown, or notional thresholds on the "
                "same frozen windows; a retry needs forward replacement rows "
                "or a richer PIT sector/industry relation source."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. Live "
                "activation would require closed forward replacement-value "
                "rows and a separate Gate 1-4 trade adapter."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "sector_etf_by_sector": SECTOR_ETF_BY_SECTOR,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_etf_signal_return": MIN_ETF_SIGNAL_RETURN,
        "min_etf_relative_vs_spy": MIN_ETF_RELATIVE_VS_SPY,
        "min_etf_close_location": MIN_ETF_CLOSE_LOCATION,
        "min_etf_ret20_excess_spy": MIN_ETF_RET20_EXCESS_SPY,
        "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
        "max_candidate_relative_vs_etf": MAX_CANDIDATE_RELATIVE_VS_ETF,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
        "max_candidate_ret5": MAX_CANDIDATE_RET5,
        "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].update(
        {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only sector ETF lead / same-sector stock laggard paper "
                "overlay"
            ),
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "sector_etf_context_tickers": sorted(SECTOR_ETF_TICKERS),
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
            "entry/candidate_pool: when a defensive/energy sector ETF leads "
            "SPY after the close, same-sector liquid stocks with positive but "
            "lagging same-day reaction may continue at the next open."
        ),
        "2_history_check": {
            "exp-20260430-008": (
                "Adding sector ETFs directly was rejected; this run does not "
                "trade ETFs and uses them only as relation context."
            ),
            "exp-20260515-017": (
                "Sector ETF candidate pool work did not promote direct ETF "
                "members. This run selects same-sector stocks only."
            ),
            "exp-20260511-024": (
                "Energy XLE/USO pair-confirmed core risk allocation was a "
                "sector-state scalar; this run is a separate default-off "
                "candidate source and covers XLE/XLP/XLU/XLV relation contexts."
            ),
            "exp-20260606-024": (
                "Rolling-correlation peer shock passed as a relation-aware "
                "free-OHLCV lead. This run tests a different ETF-to-stock "
                "relation rather than another peer-shock threshold."
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
            "exp_20260606_029_sector_etf_lead_laggard_candidate_pool.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate2"]["runtime_fields"] = [
        "warehouse ohlcv Date/Open/High/Low/Close/Volume",
        "SPY daily OHLCV",
        "XLE/XLP/XLU/XLV daily OHLCV",
        "data/reference/broad_market_sector_map.json sector/status",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The sector ETF laggard "
        "candidate source is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
    )
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted"
        if payload["gate4"]["passed"]
        else "rejected"
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
        "The sector ETF lead / same-sector laggard source cleared Gate 4 as a "
        "replay-only/default-off lead. No production surface was promoted; a "
        "shared adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The sector ETF lead / same-sector laggard source did not clear "
            "Gate 4; do not promote or locally retune this ETF-to-stock "
            "relation on the frozen windows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | ETF lead days | Trades |",
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
                days=scan.get("sector_etf_lead_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector ETF Lead / Same-Sector Laggard",
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
                "sector_etf_lead_day_count": payload["context_scan_by_window"][label].get(
                    "sector_etf_lead_days"
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
