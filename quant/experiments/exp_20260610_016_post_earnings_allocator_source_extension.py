"""exp-20260610-016: post-earnings source-priority allocator extension.

Replay-only alpha search. It tests one fixed source-extension hypothesis:
the accepted post-earnings underpriced drift helper may add independent
replacement value when admitted as a fixed rank-3 source family into the
accepted helper source-priority allocator.

This runner does not change production code, shared helpers, live/default
orders, core ranking, sizing, exits, LLM/news, or watchlists. A positive result
is only a replay lead until a shared historical/daily helper reproduces the
same source admission and parity tests pass. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402
import exp_20260610_014_revision_source_priority_allocator_extension as base  # noqa: E402
import post_earnings_underpriced_drift_paper_sleeve as post_earnings  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


framework = base.framework

EXPERIMENT_ID = "exp-20260610-016"
STEM = "post_earnings_allocator_source_extension"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = (
    "post_earnings_underpriced_source_family_added_to_accepted_helper_source_priority_allocator_v1"
)
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = "post_earnings_underpriced_allocator_source_extension_v1"
SOURCE_RULE_VERSION = "accepted_helper_source_priority_top1_with_post_earnings_replay_v1"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_016_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = allocator.BASE_NOTIONAL_USD
HOLD_DAYS = allocator.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = allocator.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = allocator.SAME_TICKER_COOLDOWN_DAYS

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260610-014",
    "aggregate_ev_delta": 0.9720,
    "aggregate_pnl_delta": 15197.05,
    "window_deltas": {
        "late_strong": {"ev": 0.5079, "pnl": 4879.33},
        "mid_weak": {"ev": 0.3356, "pnl": 6103.41},
        "old_thin": {"ev": 0.1285, "pnl": 4214.31},
    },
}

_ACCEPTED = deepcopy(allocator.SOURCE_PRIORITY)
SOURCE_PRIORITY: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        ("volatility_relief", {**_ACCEPTED["volatility_relief"], "rank": 1}),
        ("rolling_peer_shock", {**_ACCEPTED["rolling_peer_shock"], "rank": 2}),
        (
            "post_earnings_underpriced",
            {
                "rank": 3,
                "description": "accepted post-earnings underpriced drift",
                "accepted_experiment": "exp-20260602-026",
                "accepted_ev_delta_sum": 0.3547,
                "accepted_pnl_delta_sum": 3557.15,
            },
        ),
        ("turn_of_month", {**_ACCEPTED["turn_of_month"], "rank": 4}),
        ("industry_laggard_repair", {**_ACCEPTED["industry_laggard_repair"], "rank": 5}),
        (
            "revision_surprise_low_extension",
            {**_ACCEPTED["revision_surprise_low_extension"], "rank": 6},
        ),
        ("compression", {**_ACCEPTED["compression"], "rank": 7}),
        (
            "industry_stable_core_flow",
            {**_ACCEPTED["industry_stable_core_flow"], "rank": 8},
        ),
    ]
)

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_allocator_window_comparator_regression",
        "source_overlap_displaces_better_rows",
        "post_earnings_sample_too_thin",
        "earnings_snapshot_data_shape_gap",
    ],
    "confidence_reason": (
        "The post-earnings underpriced helper is an accepted shared default-off "
        "source with all three windows positive, but the current accepted "
        "allocator is a high comparator and source extensions often fail by "
        "overlapping or displacing better rows."
    ),
    "recorded_at": "2026-06-10T14:03:47+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_source_extension_scout",
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
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": 1,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "max_active_positions": 8,
        "liquidity_source": "accepted post-earnings helper liquidity gates plus next-open paper fill",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation envelope pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes in this scout",
        "failure_handling": "missing earnings snapshots or OHLCV rows create rejected source candidates only",
    },
    "parity_note": (
        "This experiment changes no production code. It rebuilds accepted helper "
        "source rows in a replay runner and adds post-earnings underpriced drift "
        "rows from the existing shared daily candidate builder. A positive result "
        "would require adding the source to the shared allocator helper, daily "
        "snapshot wiring, and parity tests before retention."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate-pool/allocation alpha: accepted post-earnings underpriced "
        "drift rows may add an event-information source to the accepted "
        "source-priority allocator, filling dates where pure OHLCV/revision "
        "helpers are absent or weaker."
    ),
    "2_history_check": {
        "exp-20260602-026": (
            "Accepted post-earnings underpriced drift shared adapter: aggregate "
            "EV +0.3547, PnL +$3,557.15, all three windows positive."
        ),
        "exp-20260610-014": (
            "Current accepted allocator with revision source: aggregate EV "
            "+0.9720 and PnL +$15,197.05. This is the binding comparator."
        ),
        "exp-20260610-006": (
            "Rejected macro-relief source extension because it failed the "
            "accepted allocator comparator."
        ),
        "exp-20260610-009": (
            "Rejected 52-week source extension despite positive aggregate "
            "because a comparator window regressed."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md canonical three windows. Must improve aggregate "
        "EV/PnL, have no EV/PnL regression windows, satisfy sample/survival/"
        "drawdown/concentration guards, and beat exp-20260610-014 aggregate "
        "and per-window EV/PnL comparator. A pass is only a replay lead until "
        "shared helper parity is implemented."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_016_post_earnings_allocator_source_extension.py"
    ),
}


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _core_entry_tickers_by_date(
    core_entries_by_date: dict[str, list[dict[str, Any]]],
) -> dict[str, list[str]]:
    return {
        date_value: sorted(
            {
                str(row.get("ticker") or "").upper()
                for row in rows
                if str(row.get("ticker") or "").strip()
            }
        )
        for date_value, rows in core_entries_by_date.items()
    }


def _sector_by_ticker(sector_entries: dict[str, dict[str, Any]]) -> dict[str, str]:
    return {
        ticker: str(meta.get("sector"))
        for ticker, meta in sector_entries.items()
        if meta.get("sector")
    }


def _source_score(row: dict[str, Any]) -> float:
    for key in (
        "candidate_score",
        "post_earnings_positive_surprise_drift_score",
        "paper_candidate_score",
        "peer_shock_score",
        "compression_score",
        "source_score",
        "score",
        "rank_score",
    ):
        if row.get(key) is not None:
            return _float(row.get(key))
    return 0.0


def _allocator_score(row: dict[str, Any]) -> float:
    rank = max(1, int(row.get("source_priority_rank") or 999))
    return _round(1000.0 / rank + _float(row.get("source_priority_score")), 6) or 0.0


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    source_family = str(row.get("source_family") or "unknown")
    return f"ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}:{source_family}"


def _renormalise_source_row(row: dict[str, Any], source_family: str | None = None) -> dict[str, Any]:
    family = str(source_family or row.get("source_family") or "")
    if family not in SOURCE_PRIORITY:
        return {}
    meta = SOURCE_PRIORITY[family]
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    score = _source_score(row)
    uses_non_ohlcv = family in {"revision_surprise_low_extension", "post_earnings_underpriced"}
    return {
        **deepcopy(row),
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "source_family": family,
        "source_priority_rank": meta["rank"],
        "source_priority_accepted_experiment": meta["accepted_experiment"],
        "source_priority_score": _round(score, 6),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": not uses_non_ohlcv,
        "uses_free_non_ohlcv": uses_non_ohlcv,
    }


def _paper_trade_from_post_earnings_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    window_end: str,
) -> dict[str, Any] | None:
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    signal_date = str(candidate.get("date") or candidate.get("signal_date") or "")[:10]
    idx = post_earnings._row_index(rows).get(signal_date)
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + HOLD_DAYS
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    exit_date = str(rows[exit_idx].get("date") or "")[:10]
    if exit_date > window_end:
        return None
    entry_raw = post_earnings._positive_float(rows[entry_idx].get("open"))
    exit_raw = post_earnings._positive_float(rows[exit_idx].get("close"))
    if not entry_raw or not exit_raw:
        return None
    entry_price = post_earnings.apply_entry_fill(entry_raw)
    exit_price = post_earnings.apply_slippage(
        exit_raw,
        post_earnings.SLIPPAGE_BPS_TARGET,
        "sell",
    )
    pnl_pct_net = (exit_price / entry_price) - 1.0 - post_earnings.ROUND_TRIP_COST_PCT
    pnl = BASE_NOTIONAL_USD * pnl_pct_net
    trade = {
        **deepcopy(candidate),
        "source": "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER",
        "source_family": "post_earnings_underpriced",
        "source_rule_version": post_earnings.SOURCE_RULE_VERSION,
        "rule_version": post_earnings.RULE_VERSION,
        "source_score": _round(_source_score(candidate), 6),
        "candidate_score": _round(_source_score(candidate), 6),
        "signal_date": signal_date,
        "date": signal_date,
        "entry_date": str(rows[entry_idx].get("date") or "")[:10],
        "exit_date": exit_date,
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": HOLD_DAYS,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "notional_usd": BASE_NOTIONAL_USD,
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "paper_pnl": _round(pnl, 2),
        "trade_enabled": False,
        "alters_orders": False,
    }
    return _renormalise_source_row(trade, "post_earnings_underpriced")


def _post_earnings_source_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = {
        **post_earnings.DEFAULT_CONFIG,
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "daily_entry_slots": 999,
        "hold_days": HOLD_DAYS,
        "core_entry_tickers_by_date": _core_entry_tickers_by_date(core_entries_by_date),
        "sector_by_ticker": _sector_by_ticker(sector_entries),
    }
    candidates, rejected, audit = (
        post_earnings.build_post_earnings_underpriced_drift_candidates_for_dates(
            as_of_dates=dates,
            ohlcv_by_ticker=rows_by_ticker,
            candidate_universe=candidate_universe,
            config=config,
        )
    )
    normalised_rows = {
        ticker: post_earnings._normalise_ohlcv_rows(rows)
        for ticker, rows in rows_by_ticker.items()
    }
    trades: list[dict[str, Any]] = []
    missing_trade_count = 0
    for candidate in candidates:
        trade = _paper_trade_from_post_earnings_candidate(
            rows_by_ticker=normalised_rows,
            candidate=candidate,
            window_end=str(window["end"]),
        )
        if trade is None:
            missing_trade_count += 1
            rejected.append({**candidate, "filter_reason": "missing_next_open_or_exit"})
            continue
        trades.append(trade)
    return trades, {
        "rule_version": post_earnings.RULE_VERSION,
        "source_rule_version": post_earnings.SOURCE_RULE_VERSION,
        "candidate_count": len(candidates),
        "trade_count": len(trades),
        "missing_trade_count": missing_trade_count,
        "rejected_count": len(rejected),
        "scan": audit,
        "source_caveat": (
            "Rows are rebuilt from the accepted shared daily post-earnings "
            "candidate builder; this runner adds historical trade conversion "
            "locally, so a positive result is not retained until shared "
            "historical/daily allocator parity is implemented."
        ),
    }


def _select_priority_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        _renormalise_source_row(row)
        for row in source_rows
        if str(row.get("source_family") or "") in SOURCE_PRIORITY
    ]
    candidates = [row for row in candidates if row]
    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or "")[:10],
            int(row.get("source_priority_rank") or 999),
            -_float(row.get("source_priority_score")),
            str(row.get("ticker") or ""),
        )
    )
    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: Counter[str] = Counter()
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("signal_date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts[signal_date] >= MAX_PAPER_TRADES_PER_DAY:
            rejected.append({**row, "filter_reason": "daily_top1_source_priority_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        out = {
            **deepcopy(row),
            "source": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "sleeve": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "decision_id": _decision_id(row),
            "candidate_score": _allocator_score(row),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "notional_usd": BASE_NOTIONAL_USD,
            "paper_status": "closed",
            "trade_enabled": False,
            "alters_orders": False,
        }
        selected.append(out)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    audit = {
        "source_candidate_count": len(candidates),
        "selected_priority_trade_count": len(selected),
        "filtered_priority_candidate_count": len(rejected),
        "source_candidate_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in candidates)
        ),
        "selected_source_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in selected)
        ),
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    }
    return selected, rejected, audit


def _build_extended_source_trades(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    label: str,
    cfg: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing_rows, existing_audit = base._build_extended_source_trades(
        snapshot=snapshot,
        dates=dates,
        label=label,
        cfg=cfg,
        core_entries_by_date=core_entries_by_date,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
    )
    existing_rows = [
        row
        for row in (_renormalise_source_row(row) for row in existing_rows)
        if row
    ]
    post_rows, post_audit = _post_earnings_source_trades(
        rows_by_ticker=snapshot,
        dates=dates,
        window=cfg,
        core_entries_by_date=core_entries_by_date,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
    )
    source_rows = existing_rows + post_rows
    source_trade_counts = OrderedDict(
        (source, len([row for row in source_rows if row.get("source_family") == source]))
        for source in SOURCE_PRIORITY
    )
    raw_candidate_counts = OrderedDict()
    for source in SOURCE_PRIORITY:
        if source == "post_earnings_underpriced":
            raw_candidate_counts[source] = post_audit["candidate_count"]
        else:
            raw_candidate_counts[source] = existing_audit.get("raw_candidate_counts", {}).get(source)
    source_audits = dict(existing_audit.get("source_audits", {}))
    source_audits["post_earnings_underpriced"] = post_audit
    return source_rows, {
        "source_priority": SOURCE_PRIORITY,
        "source_trade_counts": dict(source_trade_counts),
        "raw_candidate_counts": dict(raw_candidate_counts),
        "source_audits": source_audits,
        "extension_policy": {
            "post_earnings_underpriced_rank": SOURCE_PRIORITY["post_earnings_underpriced"]["rank"],
            "rank_reason": (
                "Inserted by accepted standalone aggregate EV between rolling "
                "peer shock and turn-of-month. No source thresholds, notional, "
                "hold, top-N, or cooldown are tuned."
            ),
        },
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    window_rows: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    aggregate_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    aggregate_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if aggregate_ev <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate_pnl <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if aggregate_ev <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]:
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if aggregate_pnl <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, row in window_rows.items():
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if float(delta.get("total_pnl") or 0.0) < comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_post_earnings_allocator_extension"
            if passed
            else "rejected_post_earnings_allocator_extension"
        ),
        "failed_reasons": failed,
        "comparator_regressions": comparator_regressions,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_candidates_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] post-earnings source-priority allocator extension")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        dates = [
            day
            for day in framework.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        source_trades, source_audit = _build_extended_source_trades(
            snapshot=snapshot,
            dates=dates,
            label=label,
            cfg=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
        )
        selected, filtered, priority_audit = _select_priority_rows(
            source_rows=source_trades,
            trading_dates=dates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected
        filtered_candidates_by_window[label] = filtered[:100]
        source_audit_by_window[label] = source_audit
        priority_audit_by_window[label] = priority_audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "all_source_trade_count": len(source_trades),
            "source_trade_counts": source_audit["source_trade_counts"],
            "raw_source_candidate_counts": source_audit["raw_candidate_counts"],
            "selected_source_counts": priority_audit["selected_source_counts"],
            "filtered_priority_candidate_count": len(filtered),
            "post_earnings_selected_count": priority_audit["selected_source_counts"].get(
                "post_earnings_underpriced",
                0,
            ),
            "post_earnings_source_trade_count": source_audit["source_trade_counts"].get(
                "post_earnings_underpriced",
                0,
            ),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        window_rows=window_rows,
    )
    passed = bool(gate4["passed"])
    status = "positive_replay_lead_not_promoted" if passed else "rejected"
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": passed,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
            6,
        ),
    }
    if passed:
        interpretation = (
            "Post-earnings underpriced rows beat the accepted allocator comparator "
            "as a replay lead, but no shared allocator policy changed."
        )
        reflection = (
            "The post-earnings rows added event-confirmed replacement value on "
            "dates where higher-priority source rows were absent or weaker. "
            "This remains a lead because the allocator helper and daily snapshot "
            "do not yet include the source family."
        )
    else:
        interpretation = (
            "The post-earnings source extension failed to beat the current "
            "accepted source-priority allocator comparator."
        )
        reflection = (
            "The standalone post-earnings sleeve remains accepted, but its rows "
            "did not add enough incremental replacement value after the accepted "
            "allocator's higher-priority rows and same-ticker cooldown. The likely "
            "failure mode is overlap/displacement, not a defect in the original "
            "post-earnings helper."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "replay_only_candidate_pool_source_extension_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_event_source_family_extension_scout",
        "nearby_prior_experiments": [
            "exp-20260602-026",
            "exp-20260610-005",
            "exp-20260610-014",
            "exp-20260610-006",
            "exp-20260610-009",
        ],
        "prior_trial_count": 5,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only post-earnings source-family extension over the "
                "accepted helper source-priority allocator"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "earnings_snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Existing accepted allocator source rows are rebuilt through "
                "the accepted helper. Post-earnings rows are generated from the "
                "accepted shared daily candidate builder and converted to fixed "
                "$4,000 next-open/10-trading-day paper trades in this runner."
            ),
        },
        "parameters": {
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "source_priority": SOURCE_PRIORITY,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "accepted helper source rows with signal_date/ticker/source_family",
                "daily earnings snapshots with positive surprise and event dates",
                "post-earnings rows with entry_date, exit_date, entry_price, exit_price, pnl",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live candidate ranking changed. The source "
                "extension is replay-only/default-off paper, so core signals "
                "generated and survived are unchanged from baseline."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "filtered_priority_candidates_by_window": filtered_candidates_by_window,
        "source_audit_by_window": source_audit_by_window,
        "priority_audit_by_window": priority_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "post_earnings_underpriced_standalone": {
                "experiment_id": "exp-20260602-026",
                "aggregate_ev_delta": 0.3547,
                "aggregate_pnl_delta": 3557.15,
            },
            "included_source_priority": SOURCE_PRIORITY,
        },
        "interpretation": interpretation,
        "rejection_reason": None if passed else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing post-earnings source rank, "
                "post-earnings helper thresholds, allocator top-N, notional, "
                "hold days, or cooldown on the same frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs closed forward allocator displacement rows, a "
                "shared historical/daily post-earnings allocator helper, or a "
                "materially different event-quality field rather than source "
                "priority retuning."
            ),
        },
        "anti_js": "No JavaScript was used.",
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
    }


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | Trades | PE selected | Top source |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        selected_counts = row["selected_source_counts"]
        top_source = "none"
        if selected_counts:
            top_source = sorted(selected_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {trades} | {pe_trades} | {top_source} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                trades=row["target_trade_count"],
                pe_trades=row["post_earnings_selected_count"],
                top_source=top_source,
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Allocator Source Extension",
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
            "- Aggregate EV delta: `{:+.4f}` versus accepted allocator `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` versus accepted allocator `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "shared_adapter_required": bool(payload["gate4"]["passed"]),
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
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
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "source_trade_count": payload["window_rows"][label]["all_source_trade_count"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "post_earnings_selected_count": payload["window_rows"][label][
                    "post_earnings_selected_count"
                ],
                "post_earnings_source_trade_count": payload["window_rows"][label][
                    "post_earnings_source_trade_count"
                ],
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
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
        "production_accepted": False,
        "shared_adapter_required": bool(payload["gate4"]["passed"]),
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

    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
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
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": payload["related_files"],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)
    print(
        "completed {experiment_id}: {decision} | dEV={ev:+.4f} | dPnL=${pnl:+,.2f}".format(
            experiment_id=EXPERIMENT_ID,
            decision=payload["decision"],
            ev=payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
            pnl=payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
        )
    )


if __name__ == "__main__":
    main()
