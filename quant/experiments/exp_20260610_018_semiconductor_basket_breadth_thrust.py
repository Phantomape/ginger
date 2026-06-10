"""exp-20260610-018: semiconductor basket breadth-thrust candidate pool.

Replay-only alpha search on a fixed free-OHLCV AI/semiconductor hardware
basket. The bundle tests whether internal basket thrust versus QQQ/SPY can
identify liquid component leaders with next-open 10-trading-day replacement
value. This is not a production adapter and does not change live/default
orders, core ranking, sizing, exits, LLM/news behavior, watchlists, or run.py.

No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260610_003_industry_leadership_dispersion as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260610-018"
STEM = "semiconductor_basket_breadth_thrust"
TRIAL_FAMILY = "semiconductor_basket_breadth_thrust_candidate_pool"
TRIAL_VARIANT_ID = "semiconductor_basket_breadth_thrust_top1_next_open_10d_v1"
CHANGED_VARIABLE = "semiconductor_basket_breadth_thrust_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_018_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 12

THEME_BASKET = ("NVDA", "AMD", "AVGO", "MU", "TSM", "CRDO")
MIN_AVAILABLE_COMPONENTS = 5
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 80_000_000.0

MIN_THEME_SIGNAL_POSITIVE_FRACTION = 0.60
MIN_THEME_RET5_POSITIVE_FRACTION = 0.60
MIN_THEME_MEDIAN_SIGNAL_EXCESS_QQQ = 0.0015
MIN_THEME_MEDIAN_RET5_EXCESS_QQQ = 0.0020
MIN_THEME_MEDIAN_RET20_EXCESS_SPY = -0.0300
MAX_THEME_MEDIAN_RET20_EXCESS_SPY = 0.1800
MIN_THEME_MEDIAN_RET60_EXCESS_SPY = -0.0600

MIN_CANDIDATE_SIGNAL_RETURN = 0.0030
MAX_CANDIDATE_SIGNAL_RETURN = 0.0950
MIN_CANDIDATE_SIGNAL_EXCESS_SPY = 0.0030
MIN_CANDIDATE_SIGNAL_EXCESS_QQQ = 0.0000
MIN_CANDIDATE_RET5_EXCESS_QQQ = 0.0010
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.0500
MAX_CANDIDATE_RET20_EXCESS_SPY = 0.2800
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.1200
MIN_CANDIDATE_CLOSE_LOCATION = 0.62
MIN_CANDIDATE_VOLUME_RATIO_20D = 0.65
MAX_CANDIDATE_VOLUME_RATIO_20D = 3.20
MAX_CANDIDATE_REALIZED_VOL_20D = 0.110

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR = (
    previous.ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR
)
ACCEPTED_ROLLING_CORR_COMPARATOR = previous.ACCEPTED_ROLLING_CORR_COMPARATOR
ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_SOURCE_PRIORITY_COMPARATOR = {
    "experiment_id": "exp-20260610-014",
    "decision": "accepted_revision_source_priority_allocator_shared_default_off",
    "expected_value_score_delta_sum": 0.9720,
    "total_pnl_delta_sum": 15197.05,
    "target_trade_count": 330,
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_technology_momentum_relabel",
        "accepted_relation_comparator_not_beaten",
        "current_source_priority_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "semiconductor_theme_concentration",
    ],
    "confidence_reason": (
        "Semiconductor/AI hardware components can receive concentrated "
        "institutional flow before every component reacts, and internal breadth "
        "versus QQQ/SPY is point-in-time free OHLCV. The warehouse lacks "
        "SMH/SOXX, so this is a fixed-basket replay scout rather than a "
        "shared-paper-first adapter. Main risk: it is merely high-beta tech "
        "momentum already captured by accepted source/relation sleeves."
    ),
    "recorded_at": "2026-06-10T16:06:08+00:00",
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
        "Replay-only scout. This experiment changes no production code. A "
        "positive result would require a shared default-off adapter computing "
        "the same fixed basket membership, SPY/QQQ-relative theme breadth, "
        "liquid component leadership fields, same-ticker core-overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, accepted comparator checks, and concentration controls in "
        "both historical replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _ticker_metrics(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    min_idx = max(60, 20, 5)
    if (
        idx is None
        or spy_idx is None
        or qqq_idx is None
        or idx < min_idx
        or spy_idx < min_idx
        or qqq_idx < min_idx
    ):
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret5 = framework._ret(spy_rows, spy_idx, 5)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    qqq_ret5 = framework._ret(qqq_rows, qqq_idx, 5)
    qqq_ret20 = framework._ret(qqq_rows, qqq_idx, 20)
    qqq_ret60 = framework._ret(qqq_rows, qqq_idx, 60)
    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    qqq_signal_return = framework._daily_return(qqq_rows, qqq_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    required = [
        ret5,
        ret20,
        ret60,
        spy_ret5,
        spy_ret20,
        spy_ret60,
        qqq_ret5,
        qqq_ret20,
        qqq_ret60,
        signal_return,
        spy_signal_return,
        qqq_signal_return,
        close_location,
        volume_ratio,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None

    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret5 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert qqq_ret5 is not None
    assert qqq_ret20 is not None
    assert qqq_ret60 is not None
    assert signal_return is not None
    assert spy_signal_return is not None
    assert qqq_signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert realized_vol20 is not None
    return {
        "date": signal_date,
        "ticker": ticker,
        "close": float(close),
        "adv20": float(adv20),
        "ret5_excess_spy": ret5 - spy_ret5,
        "ret20_excess_spy": ret20 - spy_ret20,
        "ret60_excess_spy": ret60 - spy_ret60,
        "ret5_excess_qqq": ret5 - qqq_ret5,
        "ret20_excess_qqq": ret20 - qqq_ret20,
        "ret60_excess_qqq": ret60 - qqq_ret60,
        "signal_return": signal_return,
        "signal_relative_vs_spy": signal_return - spy_signal_return,
        "signal_relative_vs_qqq": signal_return - qqq_signal_return,
        "close_location": close_location,
        "volume_ratio_20d": volume_ratio,
        "realized_vol_20d": realized_vol20,
    }


def _theme_summary(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(rows) < MIN_AVAILABLE_COMPONENTS:
        return None
    signal_excess_qqq = [float(row["signal_relative_vs_qqq"]) for row in rows]
    ret5_excess_qqq = [float(row["ret5_excess_qqq"]) for row in rows]
    ret20_excess_spy = [float(row["ret20_excess_spy"]) for row in rows]
    ret60_excess_spy = [float(row["ret60_excess_spy"]) for row in rows]
    signal_positive_fraction = sum(value > 0.0 for value in signal_excess_qqq) / len(
        signal_excess_qqq
    )
    ret5_positive_fraction = sum(value > 0.0 for value in ret5_excess_qqq) / len(
        ret5_excess_qqq
    )
    summary = {
        "available_components": len(rows),
        "median_signal_excess_qqq": median(signal_excess_qqq),
        "median_ret5_excess_qqq": median(ret5_excess_qqq),
        "median_ret20_excess_spy": median(ret20_excess_spy),
        "median_ret60_excess_spy": median(ret60_excess_spy),
        "signal_positive_fraction": signal_positive_fraction,
        "ret5_positive_fraction": ret5_positive_fraction,
        "breadth_acceleration": signal_positive_fraction - ret5_positive_fraction,
    }
    if summary["signal_positive_fraction"] < MIN_THEME_SIGNAL_POSITIVE_FRACTION:
        return None
    if summary["ret5_positive_fraction"] < MIN_THEME_RET5_POSITIVE_FRACTION:
        return None
    if summary["median_signal_excess_qqq"] < MIN_THEME_MEDIAN_SIGNAL_EXCESS_QQQ:
        return None
    if summary["median_ret5_excess_qqq"] < MIN_THEME_MEDIAN_RET5_EXCESS_QQQ:
        return None
    if summary["median_ret20_excess_spy"] < MIN_THEME_MEDIAN_RET20_EXCESS_SPY:
        return None
    if summary["median_ret20_excess_spy"] > MAX_THEME_MEDIAN_RET20_EXCESS_SPY:
        return None
    if summary["median_ret60_excess_spy"] < MIN_THEME_MEDIAN_RET60_EXCESS_SPY:
        return None
    return summary


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    theme: dict[str, Any],
) -> dict[str, Any] | None:
    if float(metrics["signal_return"]) < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if float(metrics["signal_return"]) > MAX_CANDIDATE_SIGNAL_RETURN:
        return None
    if float(metrics["signal_relative_vs_spy"]) < MIN_CANDIDATE_SIGNAL_EXCESS_SPY:
        return None
    if float(metrics["signal_relative_vs_qqq"]) < MIN_CANDIDATE_SIGNAL_EXCESS_QQQ:
        return None
    if float(metrics["ret5_excess_qqq"]) < MIN_CANDIDATE_RET5_EXCESS_QQQ:
        return None
    if float(metrics["ret20_excess_spy"]) < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if float(metrics["ret20_excess_spy"]) > MAX_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if float(metrics["ret60_excess_spy"]) < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if float(metrics["close_location"]) < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if float(metrics["volume_ratio_20d"]) < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if float(metrics["volume_ratio_20d"]) > MAX_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if float(metrics["realized_vol_20d"]) > MAX_CANDIDATE_REALIZED_VOL_20D:
        return None

    liquidity_score = math.log10(max(float(metrics["adv20"]), 1.0) / 1_000_000.0)
    extension_penalty = max(float(metrics["ret20_excess_spy"]) - 0.1800, 0.0)
    score = (
        1.25 * float(metrics["ret5_excess_qqq"])
        + 1.00 * float(metrics["signal_relative_vs_qqq"])
        + 0.55 * float(metrics["ret20_excess_qqq"])
        + 0.35 * float(metrics["ret60_excess_qqq"])
        + 0.35 * float(metrics["close_location"])
        + 0.22 * float(theme["median_ret5_excess_qqq"])
        + 0.20 * float(theme["median_signal_excess_qqq"])
        + 0.04 * liquidity_score
        - 0.40 * float(metrics["realized_vol_20d"])
        - 0.07 * abs(float(metrics["volume_ratio_20d"]) - 1.20)
        - 0.35 * extension_penalty
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": "SEMICONDUCTOR_BASKET_BREADTH_THRUST_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": "fixed_ai_semiconductor_hardware_basket",
        "candidate_signal_day_return": round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": round(
            metrics["signal_relative_vs_spy"], 6
        ),
        "candidate_signal_relative_vs_qqq": round(
            metrics["signal_relative_vs_qqq"], 6
        ),
        "candidate_ret5_excess_spy": round(metrics["ret5_excess_spy"], 6),
        "candidate_ret20_excess_spy": round(metrics["ret20_excess_spy"], 6),
        "candidate_ret60_excess_spy": round(metrics["ret60_excess_spy"], 6),
        "candidate_ret5_excess_qqq": round(metrics["ret5_excess_qqq"], 6),
        "candidate_ret20_excess_qqq": round(metrics["ret20_excess_qqq"], 6),
        "candidate_ret60_excess_qqq": round(metrics["ret60_excess_qqq"], 6),
        "candidate_close_location": round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": round(metrics["adv20"], 2),
        "theme_context": {
            "group_key": "fixed_ai_semiconductor_hardware_basket",
            "basket_members": list(THEME_BASKET),
            "available_components": theme["available_components"],
            "median_signal_excess_qqq": round(
                theme["median_signal_excess_qqq"], 6
            ),
            "median_ret5_excess_qqq": round(theme["median_ret5_excess_qqq"], 6),
            "median_ret20_excess_spy": round(theme["median_ret20_excess_spy"], 6),
            "median_ret60_excess_spy": round(theme["median_ret60_excess_spy"], 6),
            "signal_positive_fraction": round(
                theme["signal_positive_fraction"], 6
            ),
            "ret5_positive_fraction": round(theme["ret5_positive_fraction"], 6),
            "breadth_acceleration": round(theme["breadth_acceleration"], 6),
            "rule_version": RULE_VERSION,
        },
        "sector": "Information Technology",
        "industry": "Semiconductors and AI infrastructure",
        "sector_coverage_status": "fixed_basket_free_ohlcv",
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
    del sector_entries
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

    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    candidate_tickers: set[str] = set()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_theme_thrust": 0,
        "days_with_raw_candidates": 0,
        "theme_member_rows": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }

    for signal_date in dates:
        metrics_rows = [
            metrics
            for ticker in THEME_BASKET
            if (
                metrics := _ticker_metrics(
                    snapshot=snapshot,
                    indices=indices,
                    ticker=ticker,
                    signal_date=signal_date,
                )
            )
            is not None
        ]
        theme = _theme_summary(metrics_rows)
        if theme is None:
            continue
        scan["days_with_theme_thrust"] += 1
        scan["theme_member_rows"] += len(metrics_rows)

        day_rows: list[dict[str, Any]] = []
        for metrics in metrics_rows:
            row = _candidate_from_metrics(metrics=metrics, theme=theme)
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == row["ticker"] for trade in ab_entries
            )
            day_rows.append(row)
            candidate_tickers.add(str(row["ticker"]))

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_ret5_excess_qqq"]),
                -float(row["candidate_signal_relative_vs_qqq"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_candidates"] += 1
        scan["raw_candidate_rows"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_score": top["candidate_score"],
                "top_ret5_excess_qqq": top["candidate_ret5_excess_qqq"],
                "top_signal_relative_vs_qqq": top[
                    "candidate_signal_relative_vs_qqq"
                ],
                "theme_available_components": top["theme_context"][
                    "available_components"
                ],
                "theme_signal_positive_fraction": top["theme_context"][
                    "signal_positive_fraction"
                ],
                "theme_ret5_positive_fraction": top["theme_context"][
                    "ret5_positive_fraction"
                ],
                "theme_median_ret5_excess_qqq": top["theme_context"][
                    "median_ret5_excess_qqq"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_ret5_excess_qqq"]),
            -float(row["candidate_signal_relative_vs_qqq"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    scan.update(
        {
            "basket_members": list(THEME_BASKET),
            "min_available_components": MIN_AVAILABLE_COMPONENTS,
            "min_theme_signal_positive_fraction": MIN_THEME_SIGNAL_POSITIVE_FRACTION,
            "min_theme_ret5_positive_fraction": MIN_THEME_RET5_POSITIVE_FRACTION,
            "min_theme_median_signal_excess_qqq": MIN_THEME_MEDIAN_SIGNAL_EXCESS_QQQ,
            "min_theme_median_ret5_excess_qqq": MIN_THEME_MEDIAN_RET5_EXCESS_QQQ,
            "min_theme_median_ret20_excess_spy": MIN_THEME_MEDIAN_RET20_EXCESS_SPY,
            "max_theme_median_ret20_excess_spy": MAX_THEME_MEDIAN_RET20_EXCESS_SPY,
            "min_theme_median_ret60_excess_spy": MIN_THEME_MEDIAN_RET60_EXCESS_SPY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_signal_excess_spy": MIN_CANDIDATE_SIGNAL_EXCESS_SPY,
            "min_candidate_signal_excess_qqq": MIN_CANDIDATE_SIGNAL_EXCESS_QQQ,
            "min_candidate_ret5_excess_qqq": MIN_CANDIDATE_RET5_EXCESS_QQQ,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
            "max_candidate_volume_ratio_20d": MAX_CANDIDATE_VOLUME_RATIO_20D,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            "unique_candidate_tickers": len(candidate_tickers),
        }
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
    comparators = {
        "compression": ACCEPTED_COMPRESSION_COMPARATOR,
        "industry_laggard_repair": ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR,
        "rolling_corr_peer_shock": ACCEPTED_ROLLING_CORR_COMPARATOR,
        "source_priority_allocator": ACCEPTED_SOURCE_PRIORITY_COMPARATOR,
    }
    for name, comparator in comparators.items():
        if aggregate["expected_value_score_delta_sum"] <= comparator[
            "expected_value_score_delta_sum"
        ]:
            gate.setdefault("failed_reasons", []).append(f"accepted_{name}_ev_not_beaten")
        if aggregate["total_pnl_delta_sum"] <= comparator["total_pnl_delta_sum"]:
            gate.setdefault("failed_reasons", []).append(
                f"accepted_{name}_pnl_not_beaten"
            )
    gate["accepted_comparators"] = comparators
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_semiconductor_basket_breadth_thrust"
        if gate["passed"]
        else "rejected_semiconductor_basket_breadth_thrust_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "candidate_pool/entry: when a fixed liquid AI/semiconductor "
                "hardware basket shows internal thrust versus QQQ and SPY, "
                "the strongest liquid confirming component may offer next-open "
                "10-day replacement value beyond generic broad technology "
                "momentum."
            ),
            "change_type": "default_off_paper_candidate_pool_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "free_ohlcv_fixed_theme_breadth_alpha",
            "new_evidence_type": "free_ohlcv_fixed_semiconductor_basket_breadth",
            "nearby_prior_experiments": [
                "exp-20260607-008",
                "exp-20260608-008",
                "exp-20260610-003",
                "exp-20260610-014",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": payload["gate4"]["accepted_comparators"],
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that fixed semiconductor "
                "basket breadth still relabels high-beta technology momentum, "
                "or the available free-OHLCV relation edge is already captured "
                "by accepted relation/source-priority sleeves."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT free-data evidence, such as "
                "real SMH/SOXX or industry ETF history, constituent additions, "
                "earnings/capex/catalyst provenance, borrow/options/ownership "
                "context, or closed forward replacement rows from a shared "
                "default-off adapter. Do not sweep these basket thresholds on "
                "the frozen windows."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "basket_members": list(THEME_BASKET),
            "min_available_components": MIN_AVAILABLE_COMPONENTS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_theme_signal_positive_fraction": MIN_THEME_SIGNAL_POSITIVE_FRACTION,
            "min_theme_ret5_positive_fraction": MIN_THEME_RET5_POSITIVE_FRACTION,
            "min_theme_median_signal_excess_qqq": MIN_THEME_MEDIAN_SIGNAL_EXCESS_QQQ,
            "min_theme_median_ret5_excess_qqq": MIN_THEME_MEDIAN_RET5_EXCESS_QQQ,
            "min_theme_median_ret20_excess_spy": MIN_THEME_MEDIAN_RET20_EXCESS_SPY,
            "max_theme_median_ret20_excess_spy": MAX_THEME_MEDIAN_RET20_EXCESS_SPY,
            "min_theme_median_ret60_excess_spy": MIN_THEME_MEDIAN_RET60_EXCESS_SPY,
            "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
            "max_candidate_signal_return": MAX_CANDIDATE_SIGNAL_RETURN,
            "min_candidate_signal_excess_spy": MIN_CANDIDATE_SIGNAL_EXCESS_SPY,
            "min_candidate_signal_excess_qqq": MIN_CANDIDATE_SIGNAL_EXCESS_QQQ,
            "min_candidate_ret5_excess_qqq": MIN_CANDIDATE_RET5_EXCESS_QQQ,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
            "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
            "max_candidate_volume_ratio_20d": MAX_CANDIDATE_VOLUME_RATIO_20D,
            "max_candidate_realized_vol_20d": MAX_CANDIDATE_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool/entry: fixed AI/semiconductor hardware breadth "
            "versus QQQ/SPY should capture theme-specific sponsorship and "
            "candidate leadership, not just broad index beta."
        ),
        "2_history_check": {
            "accepted_neighbors": (
                "exp-20260607-008 industry laggard repair, exp-20260608-008 "
                "industry stable core-flow, exp-20260606-025 rolling-corr peer "
                "shock, and exp-20260610-014 source-priority allocator are the "
                "comparators this scout must beat before promotion."
            ),
            "rejected_neighbors": (
                "exp-20260610-003 industry leadership dispersion and "
                "exp-20260609-019 breadth acceleration failed or were not "
                "promoted; this run uses a fixed theme basket and QQQ-relative "
                "breadth rather than PIT sector groups."
            ),
            "why_not_duplicate": (
                "This run does not retune industry group thresholds, state "
                "surface, LLM ranking, or source priority. It tests one fixed "
                "theme-basket breadth/thrust candidate source."
            ),
        },
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Require positive "
            "aggregate EV/PnL, no EV/PnL-regressed window, target sample >=20 "
            "across all 3 windows, survival unchanged above 5%, drawdown drift "
            "<=0.5pp, concentration guard pass, and aggregate EV/PnL above "
            "accepted compression, industry-laggard, rolling-corr, and "
            "source-priority comparators."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260610_018_semiconductor_basket_breadth_thrust.py"
        ),
    }
    payload["gate_questions"] = payload["pre_run_questions"]
    payload["gate2"]["field_checks"] = {
        "entry_date": "provided by shared replay framework",
        "target_price": "provided by shared replay framework",
        "basket_members_present_in_all_windows": [
            "NVDA",
            "AMD",
            "AVGO",
            "MU",
            "TSM",
            "CRDO",
        ],
        "unavailable_etf_or_equipment_history": ["SMH", "SOXX", "ASML", "LRCX", "KLAC"],
        "production_visible_inputs": ["OHLCV", "SPY", "QQQ"],
    }
    payload["gate3"]["note"] = (
        "No new core filter or live entry rule was added. The semiconductor "
        "basket source is additive replay-only/default-off paper, so core "
        "signals generated and survived are unchanged from baseline."
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior history needed for SPY/QQQ-relative returns, basket breadth, "
        "ADV, volume ratio, volatility, and close location. Paper entry is "
        "next available open with existing entry slippage; exit is the close "
        "10 trading days after signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "positive_replay_lead_not_promoted" if passed else "rejected"
    payload["interpretation"] = (
        "The semiconductor basket breadth-thrust source cleared strict Gate 4 "
        "and beat accepted comparators, but remains replay-only until a shared "
        "default-off adapter proves historical/daily parity and forward "
        "replacement value."
        if passed
        else (
            "The semiconductor basket breadth-thrust source did not clear Gate "
            "4 or did not beat accepted comparators. Do not promote it or "
            "locally retune basket breadth, candidate leadership, liquidity, "
            "hold-day, cooldown, or notional thresholds on these frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "result": payload["interpretation"],
        "why_result_happened": (
            "A fixed six-name semiconductor/AI hardware basket is a clean "
            "production-visible free-data scout, but if it fails, the mechanism "
            "likely collapsed into crowded high-beta technology momentum. The "
            "strict comparison to accepted relation/source-priority alphas "
            "prevents preserving a weaker replay-only source just because the "
            "theme is intuitively attractive."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping basket member count, breadth fractions, "
            "median QQQ/SPY thresholds, candidate ret5/ret20/ret60 bounds, "
            "volume, volatility, top-N, hold-day, cooldown, or paper notional "
            "on the same fixed windows."
        ),
        "new_evidence_required": (
            "Only revisit with materially new PIT data: SMH/SOXX history, a "
            "broader verified constituent feed, catalyst provenance, "
            "borrow/options/ownership context, or forward closed replacement "
            "rows from a shared default-off adapter."
        ),
    }
    payload["context_alias"] = "semiconductor_basket_day_contexts"
    payload["semiconductor_basket_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
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
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Semiconductor Basket Breadth-Thrust",
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
            "- Source-priority comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_SOURCE_PRIORITY_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_SOURCE_PRIORITY_COMPARATOR["total_pnl_delta_sum"],
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
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": "free_ohlcv_fixed_theme_breadth_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
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
                "raw_candidate_count": payload["raw_candidate_counts"][label],
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


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
