"""exp-20260606-004: broad 5-day winner continuation candidate pool.

Replay-only alpha search.  This tests whether the observed-only f5/h10
long-only continuation lead from exp-20260601-008 survives a production-like
next-open paper replay as a top-1 daily candidate source.

The only alpha variable is cross-sectional 5-day SPY-relative return rank on
the signal-date close.  Price, liquidity, common-stock hygiene, one-trade-per-
day, same-ticker cooldown, and same-ticker core-overlap exclusion are execution
guards.  No production code, shared adapter, live/default orders, ranking,
sizing, exits, LLM/news path, or watchlist behavior is changed.  No JavaScript
is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENTS_DIR / "legacy"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, LEGACY_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402


EXPERIMENT_ID = "exp-20260606-004"
STEM = "broad_5d_winner_continuation_candidate_pool"
TRIAL_FAMILY = "broad_full_liquid_5d_winner_continuation_candidate_pool"
TRIAL_VARIANT_ID = "top_5d_spy_relative_winner_next_open_10d_top1_v1"
CHANGED_VARIABLE = "broad_full_liquid_top_5d_spy_relative_winner_continuation_top1_candidate_pool"
RULE_VERSION = "broad_full_liquid_top_ret5_excess_spy_top1_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WAREHOUSE = REPO_ROOT / "data" / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite"

FORMATION_DAYS = 5
CORE_MOMENTUM_DAYS = 20
HOLD_DAYS = 10
TOP_BUCKET_FRACTION = 0.20
MIN_CROSS_SECTION_COUNT = 250
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
BASE_NOTIONAL_USD = 4_000.0
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "not_incremental_over_core_momentum",
        "window_regression",
        "top1_concentration",
        "chased_winner_gap_decay",
    ],
    "confidence_reason": (
        "Exp-20260601-008 found long-only f5/h10 excess but not significant "
        "ret20-incremental evidence; this run asks whether a stricter top-1, "
        "next-open paper execution can still add replacement value."
    ),
    "recorded_at": "2026-06-06T02:16:45Z",
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
        "require a shared default-off adapter that computes the same warehouse "
        "all-windows-full-liquid stock universe, 5-day SPY-relative rank, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "core-overlap controls in both replay and daily production before any "
        "report queue, paper ledger, candidate priority, sizing, watchlist, or "
        "order surface could change."
    ),
}


def _load_eligible_entries() -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    sql = """
        select u.ticker, u.title, u.tags_json
        from coverage_summary c
        join ticker_universe u on u.ticker = c.ticker
        where c.all_windows_full_liquid = 1
          and u.hygiene_pass = 1
        order by u.ticker
    """
    with sqlite3.connect(WAREHOUSE) as con:
        for ticker, title, tags_json in con.execute(sql):
            ticker_u = str(ticker).upper()
            if "." in ticker_u or "-" in ticker_u:
                continue
            try:
                tags = json.loads(tags_json or "[]")
            except json.JSONDecodeError:
                tags = []
            title_l = str(title or "").lower()
            if "etf_or_fund" in tags:
                continue
            if any(token in title_l for token in (" etf", " etn", " fund", " trust")):
                continue
            entries[ticker_u] = {
                "source": "warehouse_all_windows_full_liquid_common_stock_proxy",
                "title": title,
                "tags": tags,
            }
    return entries


def _close_return(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = framework._value(rows[idx - lookback], "Close")
    close = framework._value(rows[idx], "Close")
    if prior is None or prior <= 0 or close is None:
        return None
    return close / prior - 1.0


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    indices = {
        ticker: framework.shadow._row_index(rows)
        for ticker, rows in snapshot.items()
    }
    spy_rows = snapshot.get("SPY", [])
    spy_index = indices.get("SPY", {})

    candidates: list[dict[str, Any]] = []
    continuation_contexts: list[dict[str, Any]] = []
    scan: Counter[str] = Counter()

    for signal_date in dates:
        spy_idx = spy_index.get(signal_date)
        if spy_idx is None:
            scan["missing_spy_date"] += 1
            continue
        spy_ret5 = _close_return(spy_rows, spy_idx, FORMATION_DAYS)
        if spy_ret5 is None:
            scan["missing_spy_ret5"] += 1
            continue
        daily_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            rows = snapshot.get(ticker)
            if not rows:
                scan["missing_ticker_rows"] += 1
                continue
            idx = indices.get(ticker, {}).get(signal_date)
            if idx is None:
                scan["missing_signal_date"] += 1
                continue
            if idx < CORE_MOMENTUM_DAYS or idx + HOLD_DAYS >= len(rows):
                scan["insufficient_history_or_forward"] += 1
                continue
            exit_date = framework.shadow._date(rows[idx + HOLD_DAYS])
            if str(exit_date) > str(cfg["end"]):
                scan["exit_outside_window"] += 1
                continue
            close = framework._value(rows[idx], "Close")
            if close is None or close < MIN_PRICE:
                scan["price_below_floor"] += 1
                continue
            avg_dv = framework._avg_dollar_volume(rows, idx, CORE_MOMENTUM_DAYS)
            if avg_dv is None or avg_dv < MIN_AVG_DOLLAR_VOLUME_20D:
                scan["liquidity_below_floor"] += 1
                continue
            ret5 = _close_return(rows, idx, FORMATION_DAYS)
            ret20 = _close_return(rows, idx, CORE_MOMENTUM_DAYS)
            if ret5 is None or ret20 is None:
                scan["missing_returns"] += 1
                continue
            daily_rows.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "close": close,
                    "avg_dollar_volume_20d": avg_dv,
                    "ret5": ret5,
                    "ret20": ret20,
                    "spy_ret5": spy_ret5,
                    "ret5_excess_spy": ret5 - spy_ret5,
                }
            )
        if len(daily_rows) < MIN_CROSS_SECTION_COUNT:
            scan["thin_cross_section_day"] += 1
            continue
        daily_rows.sort(
            key=lambda row: (
                -float(row["ret5_excess_spy"]),
                -float(row["ret5"]),
                -float(row["ret20"]),
                -float(row["avg_dollar_volume_20d"]),
                str(row["ticker"]),
            )
        )
        bucket_count = max(1, math.ceil(len(daily_rows) * TOP_BUCKET_FRACTION))
        top_bucket = daily_rows[:bucket_count]
        continuation_contexts.append(
            {
                "date": signal_date,
                "cross_section_count": len(daily_rows),
                "top_bucket_count": bucket_count,
                "spy_ret5": framework._round(spy_ret5, 6),
                "top_ret5_excess_spy": framework._round(top_bucket[0]["ret5_excess_spy"], 6),
                "bucket_cutoff_ret5_excess_spy": framework._round(
                    top_bucket[-1]["ret5_excess_spy"], 6
                ),
            }
        )
        ab_entries = entries_by_date.get(signal_date, [])
        for rank, row in enumerate(top_bucket, start=1):
            ticker = str(row["ticker"]).upper()
            candidate = {
                "date": signal_date,
                "ticker": ticker,
                "source": STEM,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "candidate_score": framework._round(row["ret5_excess_spy"], 6),
                "candidate_relative_vs_spy": framework._round(row["ret5_excess_spy"], 6),
                "candidate_ret5": framework._round(row["ret5"], 6),
                "candidate_ret20": framework._round(row["ret20"], 6),
                "candidate_avg_dollar_volume_20d": framework._round(
                    row["avg_dollar_volume_20d"], 2
                ),
                "cross_section_rank": rank,
                "cross_section_rank_pct": framework._round(1.0 - ((rank - 1) / len(daily_rows)), 6),
                "top_bucket_fraction": TOP_BUCKET_FRACTION,
                "same_day_ab_entry_count": len(ab_entries),
                "same_day_ab_overlap": bool(ab_entries),
                "same_ticker_ab_overlap": any(
                    trade.get("ticker") == ticker for trade in ab_entries
                ),
                "known_at": "after_signal_date_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
            candidates.append(candidate)
    candidates.sort(
        key=lambda row: (
            row["date"],
            int(row["cross_section_rank"]),
            -float(row["candidate_score"]),
            row["ticker"],
        )
    )
    return candidates, continuation_contexts, {
        "dates_checked": len(dates),
        "candidate_count": len(candidates),
        "audit_reject_counts": dict(sorted(scan.items())),
        "rule_version": RULE_VERSION,
        "min_cross_section_count": MIN_CROSS_SECTION_COUNT,
        "top_bucket_fraction": TOP_BUCKET_FRACTION,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = framework._ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_broad_5d_winner_continuation"
        if gate["passed"]
        else "rejected_broad_5d_winner_continuation_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = framework._ORIGINAL_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Broad all-windows-full-liquid stocks in the top cross-sectional "
                "5-day SPY-relative return bucket may continue over the next "
                "10 trading days when replayed as a top-1 next-open default-off "
                "paper candidate."
            ),
            "change_type": "default_off_broad_5d_winner_continuation_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "short_formation_continuation",
            "new_evidence_type": (
                "observed_only_f5_h10_long_only_continuation_promoted_to_next_open_paper_replay"
            ),
            "nearby_prior_experiments": [
                "exp-20260601-007",
                "exp-20260601-008",
                "exp-20260602-015",
                "exp-20260605-013",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "interpretation": (
                "Rejected unless the top-1 winner-continuation paper sleeve lifts "
                "aggregate EV and PnL without any window PnL regression, material "
                "drawdown drift, or concentration failure."
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that exp-20260601-008's "
                "long-only f5/h10 lead was not incremental over ret20/core "
                "momentum; top-1 next-open execution may simply chase already "
                "extended winners and decay after costs."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "formation_days": FORMATION_DAYS,
            "core_momentum_days": CORE_MOMENTUM_DAYS,
            "hold_days": HOLD_DAYS,
            "top_bucket_fraction": TOP_BUCKET_FRACTION,
            "min_cross_section_count": MIN_CROSS_SECTION_COUNT,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: top cross-sectional 5-day SPY-relative "
            "winners in the broad full-liquid stock universe may keep "
            "continuing over the next 10 trading days."
        ),
        "2_history_check": {
            "exp-20260601-007": (
                "Rejected reversal; incidental continuation sign appeared."
            ),
            "exp-20260601-008": (
                "Observed long-only f5/h10 excess but did not prove ret20 "
                "incrementality."
            ),
            "exp-20260602-015": (
                "Stock-only RS acceleration completed but nearby broad OHLCV "
                "momentum sources carry high multiple-testing risk."
            ),
            "exp-20260605-013": (
                "Low-beta residual momentum rejected; this run tests short "
                "formation continuation directly."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_success_failure_criteria": (
            "Use docs/backtesting.md three-window before/after aggregate; accept "
            "only positive EV and PnL with no window PnL regression, drawdown "
            "drift <=0.5pp, survival >=5%, and concentration guard pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260606_004_broad_5d_winner_continuation_candidate_pool.py"
        ),
    }
    if not payload.get("gate4", {}).get("passed"):
        payload["interpretation"] = (
            "The 5-day winner-continuation candidate pool did not clear Gate 4; "
            "do not promote or retune nearby broad OHLCV momentum on these "
            "frozen windows without new forward evidence."
        )
    return payload


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
    framework._load_sector_entries = _load_eligible_entries
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload


framework._ORIGINAL_GATE4 = framework._gate4
framework._ORIGINAL_BUILD_PAYLOAD = framework._build_payload
_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
